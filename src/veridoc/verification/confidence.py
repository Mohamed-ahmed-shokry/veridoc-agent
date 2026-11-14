"""Deterministic OCR and extraction confidence threshold verification.

In Veridoc's document-intelligence pipeline, upstream stages record percentage
confidence scores (bounded ``[0, 100]``) on ``InvoiceExtraction``:

- ``ocr_confidence`` reflects the optical character recognition quality across
  decoded document pages.
- ``extraction_confidence`` reflects the structured extractor's certainty in the
  parsed invoice fields.

When either confidence score falls below an operational minimum threshold,
extracted values may still happen to satisfy arithmetic and format checks,
creating a risk of unearned ``clear`` verdicts on degraded scans or uncertain
extractions. This module routes low-confidence extractions to human review.
"""

from __future__ import annotations

from math import isfinite
from typing import Final, Literal

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.models import VerificationFinding

DEFAULT_MIN_OCR_CONFIDENCE: Final[float] = 70.0
DEFAULT_MIN_EXTRACTION_CONFIDENCE: Final[float] = 70.0


def _validate_threshold(name: str, value: float) -> None:
    if not isfinite(value) or value < 0.0 or value > 100.0:
        raise ValueError(f"{name} must be a finite number between 0 and 100.")


def _check_single_confidence(
    *,
    confidence: float | None,
    threshold: float,
    finding_type: Literal["low_ocr_confidence", "low_extraction_confidence"],
    field_name: str,
    label: str,
) -> VerificationFinding | None:
    if confidence is None or not isfinite(confidence):
        return None
    if confidence >= threshold:
        return None

    rounded_confidence = round(confidence, 2)
    rounded_threshold = round(threshold, 2)
    return VerificationFinding(
        finding_type=finding_type,
        severity="medium",
        explanation=(
            f"{label} ({rounded_confidence:.2f}%) is below the minimum threshold "
            f"({rounded_threshold:.2f}%)."
        ),
        comparison_source="invoice_fields",
        deterministic_rule=f"{field_name} >= {rounded_threshold:.2f}",
        observed_value=f"{rounded_confidence:.2f}",
        expected_value=f">= {rounded_threshold:.2f}",
        details={
            "field": field_name,
            "confidence": rounded_confidence,
            "threshold": rounded_threshold,
        },
    )


def check_confidence_thresholds(
    invoice: InvoiceExtraction,
    *,
    min_ocr_confidence: float = DEFAULT_MIN_OCR_CONFIDENCE,
    min_extraction_confidence: float = DEFAULT_MIN_EXTRACTION_CONFIDENCE,
) -> list[VerificationFinding]:
    """Flag invoices whose OCR or extraction confidence falls below threshold.

    Args:
        invoice: Extracted invoice data to verify.
        min_ocr_confidence: Minimum acceptable ``ocr_confidence`` percentage in
            ``[0, 100]``. Defaults to ``DEFAULT_MIN_OCR_CONFIDENCE`` (70.0).
        min_extraction_confidence: Minimum acceptable ``extraction_confidence``
            percentage in ``[0, 100]``. Defaults to
            ``DEFAULT_MIN_EXTRACTION_CONFIDENCE`` (70.0).

    Returns:
        A list of ``medium``-severity findings for each populated confidence
        score strictly below its threshold, ordered ``low_ocr_confidence``
        followed by ``low_extraction_confidence``.
    """
    _validate_threshold("min_ocr_confidence", min_ocr_confidence)
    _validate_threshold("min_extraction_confidence", min_extraction_confidence)

    findings: list[VerificationFinding] = []
    ocr_finding = _check_single_confidence(
        confidence=invoice.ocr_confidence,
        threshold=min_ocr_confidence,
        finding_type="low_ocr_confidence",
        field_name="ocr_confidence",
        label="OCR confidence",
    )
    if ocr_finding is not None:
        findings.append(ocr_finding)

    extraction_finding = _check_single_confidence(
        confidence=invoice.extraction_confidence,
        threshold=min_extraction_confidence,
        finding_type="low_extraction_confidence",
        field_name="extraction_confidence",
        label="Extraction confidence",
    )
    if extraction_finding is not None:
        findings.append(extraction_finding)

    return findings


__all__ = [
    "DEFAULT_MIN_EXTRACTION_CONFIDENCE",
    "DEFAULT_MIN_OCR_CONFIDENCE",
    "check_confidence_thresholds",
]
