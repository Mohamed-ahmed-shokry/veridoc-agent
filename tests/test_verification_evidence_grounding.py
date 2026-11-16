"""Unit and integration tests for extraction evidence grounding verification."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from veridoc.extraction.models import (
    EvidenceReference,
    InvoiceExtraction,
    InvoiceLineItem,
)
from veridoc.verification.evidence_grounding import (
    REQUIRED_GROUNDED_HEADER_FIELDS,
    check_evidence_grounding,
)


def _ref(text_span: str | None = "span") -> EvidenceReference:
    return EvidenceReference(page_number=1, source="ocr_text", text_span=text_span)


def _grounded_invoice(
    *,
    omit_header_evidence: tuple[str, ...] = (),
    line_item_evidence: list[EvidenceReference] | None = None,
) -> InvoiceExtraction:
    evidence: dict[str, list[EvidenceReference]] = {
        field: [_ref(f"{field}-span")]
        for field in REQUIRED_GROUNDED_HEADER_FIELDS
        if field not in omit_header_evidence
    }
    item_ev = [_ref("item-0")] if line_item_evidence is None else line_item_evidence
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
        line_items=[
            InvoiceLineItem(
                description="Consulting",
                product_identifier="CONS-1",
                quantity=Decimal(1),
                unit_price=Decimal("100.00"),
                total_price=Decimal("100.00"),
                evidence=item_ev,
            )
        ],
        evidence=evidence,
    )


def test_evidence_free_extraction_produces_no_findings() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Acme Supplies",
        invoice_number="INV-1001",
        invoice_date=date(2026, 10, 1),
        currency="USD",
        total=Decimal("110.00"),
        line_items=[
            InvoiceLineItem(description="Consulting", total_price=Decimal("100.00"))
        ],
    )
    assert check_evidence_grounding(invoice) == []


def test_fully_grounded_extraction_produces_no_findings() -> None:
    invoice = _grounded_invoice()
    assert check_evidence_grounding(invoice) == []


def test_page_image_evidence_without_text_span_is_valid() -> None:
    invoice = _grounded_invoice()
    invoice.evidence["total"] = [EvidenceReference(page_number=1, source="page_image")]
    assert check_evidence_grounding(invoice) == []


@pytest.mark.parametrize("missing_field", REQUIRED_GROUNDED_HEADER_FIELDS)
def test_missing_header_field_evidence_emits_finding(missing_field: str) -> None:
    invoice = _grounded_invoice(omit_header_evidence=(missing_field,))
    findings = check_evidence_grounding(invoice)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "ungrounded_extracted_field"
    assert finding.severity == "medium"
    assert finding.comparison_source == "invoice_fields"
    assert finding.details == {"field": missing_field, "reason": "missing_evidence"}


def test_absent_header_field_does_not_require_evidence_in_grounded_mode() -> None:
    invoice = _grounded_invoice(omit_header_evidence=("invoice_date",))
    invoice = invoice.model_copy(update={"invoice_date": None})
    assert check_evidence_grounding(invoice) == []


def test_ungrounded_line_item_emits_finding_when_header_is_grounded() -> None:
    invoice = _grounded_invoice(line_item_evidence=[])
    findings = check_evidence_grounding(invoice)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "ungrounded_extracted_field"
    assert finding.severity == "medium"
    assert finding.comparison_source == "invoice_line_items"
    assert finding.observed_value == "Consulting"
    assert finding.details == {
        "field": "line_items[0]",
        "line_item_index": 0,
        "reason": "missing_evidence",
    }


def test_line_item_evidence_activates_grounded_mode_for_headers() -> None:
    invoice = _grounded_invoice(omit_header_evidence=REQUIRED_GROUNDED_HEADER_FIELDS)
    findings = check_evidence_grounding(invoice)
    assert [f.details["field"] for f in findings] == list(
        REQUIRED_GROUNDED_HEADER_FIELDS
    )


def test_whitespace_only_text_span_is_rejected_as_invalid_evidence() -> None:
    invoice = _grounded_invoice()
    invoice.evidence["total"] = [
        EvidenceReference(page_number=1, source="ocr_text", text_span="   \t ")
    ]
    findings = check_evidence_grounding(invoice)
    assert len(findings) == 1
    assert findings[0].details == {"field": "total", "reason": "invalid_evidence"}


def test_unvalidated_page_zero_reference_is_rejected_as_invalid_evidence() -> None:
    invoice = _grounded_invoice()
    invoice.evidence["currency"] = [
        EvidenceReference.model_construct(
            page_number=0, source="ocr_text", text_span="USD"
        )
    ]
    findings = check_evidence_grounding(invoice)
    assert len(findings) == 1
    assert findings[0].details == {"field": "currency", "reason": "invalid_evidence"}


def test_mixed_invalid_and_valid_evidence_passes() -> None:
    invoice = _grounded_invoice()
    invoice.evidence["total"] = [
        EvidenceReference(page_number=1, source="ocr_text", text_span=" "),
        _ref("Total: 110.00"),
    ]
    assert check_evidence_grounding(invoice) == []


def test_check_evidence_grounding_does_not_mutate_invoice() -> None:
    invoice = _grounded_invoice(omit_header_evidence=("total",))
    snapshot = invoice.model_copy(deep=True)
    _ = check_evidence_grounding(invoice)
    assert invoice == snapshot
