"""Unit and integration tests for OCR and extraction confidence verification."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.confidence import (
    DEFAULT_MIN_EXTRACTION_CONFIDENCE,
    DEFAULT_MIN_OCR_CONFIDENCE,
    check_confidence_thresholds,
)


def _complete_invoice(
    *,
    ocr_confidence: float | None = None,
    extraction_confidence: float | None = None,
) -> InvoiceExtraction:
    return InvoiceExtraction(
        document_type="invoice",
        vendor_name="Acme Supplies",
        vendor_identifier="V-001",
        invoice_number="INV-1001",
        invoice_date=date(2026, 10, 1),
        currency="USD",
        subtotal=Decimal("100.00"),
        tax=Decimal("10.00"),
        total=Decimal("110.00"),
        ocr_confidence=ocr_confidence,
        extraction_confidence=extraction_confidence,
    )


def test_absent_confidences_produce_no_findings() -> None:
    invoice = _complete_invoice(ocr_confidence=None, extraction_confidence=None)
    assert check_confidence_thresholds(invoice) == []


@pytest.mark.parametrize(
    ("ocr_confidence", "extraction_confidence"),
    [
        (DEFAULT_MIN_OCR_CONFIDENCE, DEFAULT_MIN_EXTRACTION_CONFIDENCE),
        (70.0, None),
        (None, 70.0),
        (92.5, 88.0),
        (100.0, 100.0),
    ],
)
def test_confidences_at_or_above_threshold_produce_no_findings(
    ocr_confidence: float | None,
    extraction_confidence: float | None,
) -> None:
    invoice = _complete_invoice(
        ocr_confidence=ocr_confidence,
        extraction_confidence=extraction_confidence,
    )
    assert check_confidence_thresholds(invoice) == []


@pytest.mark.parametrize("score", [0.0, 32.5, 69.99])
def test_low_ocr_confidence_produces_finding(score: float) -> None:
    invoice = _complete_invoice(ocr_confidence=score, extraction_confidence=90.0)
    findings = check_confidence_thresholds(invoice)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "low_ocr_confidence"
    assert finding.severity == "medium"
    assert finding.comparison_source == "invoice_fields"
    assert finding.observed_value == f"{score:.2f}"
    assert finding.expected_value == ">= 70.00"
    assert finding.details == {
        "field": "ocr_confidence",
        "confidence": round(score, 2),
        "threshold": 70.0,
    }


@pytest.mark.parametrize("score", [0.0, 41.25, 69.99])
def test_low_extraction_confidence_produces_finding(score: float) -> None:
    invoice = _complete_invoice(ocr_confidence=95.0, extraction_confidence=score)
    findings = check_confidence_thresholds(invoice)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "low_extraction_confidence"
    assert finding.severity == "medium"
    assert finding.comparison_source == "invoice_fields"
    assert finding.observed_value == f"{score:.2f}"
    assert finding.expected_value == ">= 70.00"
    assert finding.details == {
        "field": "extraction_confidence",
        "confidence": round(score, 2),
        "threshold": 70.0,
    }


def test_both_low_confidences_emit_in_deterministic_order() -> None:
    invoice = _complete_invoice(ocr_confidence=55.0, extraction_confidence=60.0)
    findings = check_confidence_thresholds(invoice)
    assert [f.finding_type for f in findings] == [
        "low_ocr_confidence",
        "low_extraction_confidence",
    ]
    assert all(f.severity == "medium" for f in findings)


def test_custom_thresholds_are_respected() -> None:
    invoice = _complete_invoice(ocr_confidence=80.0, extraction_confidence=85.0)
    assert (
        check_confidence_thresholds(
            invoice, min_ocr_confidence=80.0, min_extraction_confidence=85.0
        )
        == []
    )
    findings = check_confidence_thresholds(
        invoice, min_ocr_confidence=85.0, min_extraction_confidence=90.0
    )
    assert [f.finding_type for f in findings] == [
        "low_ocr_confidence",
        "low_extraction_confidence",
    ]
    assert findings[0].details["threshold"] == 85.0
    assert findings[1].details["threshold"] == 90.0


@pytest.mark.parametrize("bad_value", [-0.01, 100.01, float("nan"), float("inf")])
def test_invalid_thresholds_raise_value_error(bad_value: float) -> None:
    invoice = _complete_invoice()
    with pytest.raises(ValueError, match="min_ocr_confidence"):
        check_confidence_thresholds(invoice, min_ocr_confidence=bad_value)
    with pytest.raises(ValueError, match="min_extraction_confidence"):
        check_confidence_thresholds(invoice, min_extraction_confidence=bad_value)


def test_non_finite_confidence_on_unvalidated_model_is_safely_ignored() -> None:
    invoice = InvoiceExtraction.model_construct(
        document_type="invoice",
        ocr_confidence=float("nan"),
        extraction_confidence=float("inf"),
        line_items=[],
        evidence={},
        uncertainties=[],
    )
    assert check_confidence_thresholds(invoice) == []


def test_check_confidence_thresholds_does_not_mutate_invoice() -> None:
    invoice = _complete_invoice(ocr_confidence=42.0, extraction_confidence=51.0)
    snapshot = invoice.model_copy(deep=True)
    _ = check_confidence_thresholds(invoice)
    assert invoice == snapshot
