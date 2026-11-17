"""Deterministic extraction evidence grounding verification.

In Veridoc's document-intelligence pipeline, structured extractors record
page-level provenance in ``InvoiceExtraction.evidence`` and
``InvoiceLineItem.evidence``. When an upstream extractor operates in
evidence-grounded mode (emitting at least one evidence entry), leaving
populated critical header fields or line items ungrounded signals potential
model hallucination or dropped provenance.

This module verifies that critical populated fields and line items carry
valid ``EvidenceReference`` entries whenever evidence grounding is active,
while passing evidence-free synthetic fixtures through unchanged.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from veridoc.extraction.models import EvidenceReference, InvoiceExtraction
from veridoc.verification.models import VerificationFinding

REQUIRED_GROUNDED_HEADER_FIELDS: Final[tuple[str, ...]] = (
    "invoice_number",
    "invoice_date",
    "currency",
    "total",
)


def _is_valid_reference(reference: EvidenceReference) -> bool:
    return reference.page_number >= 1 and (
        reference.text_span is None or bool(reference.text_span.strip())
    )


def _has_valid_evidence(references: Sequence[EvidenceReference]) -> bool:
    return any(_is_valid_reference(reference) for reference in references)


def _grounding_reason(references: Sequence[EvidenceReference]) -> str:
    return "missing_evidence" if not references else "invalid_evidence"


def check_evidence_grounding(
    invoice: InvoiceExtraction,
) -> list[VerificationFinding]:
    """Flag ungrounded critical fields and line items when evidence is present.

    Returns ``[]`` when the extraction carries no evidence anywhere
    (``not invoice.evidence`` and all line items have empty ``evidence``).
    Otherwise, returns one ``medium``-severity ``ungrounded_extracted_field``
    finding for each populated field in ``REQUIRED_GROUNDED_HEADER_FIELDS``
    and each line item that lacks a valid ``EvidenceReference``.
    """
    has_any_evidence = bool(invoice.evidence) or any(
        bool(item.evidence) for item in invoice.line_items
    )
    if not has_any_evidence:
        return []

    findings: list[VerificationFinding] = []
    for field_name in REQUIRED_GROUNDED_HEADER_FIELDS:
        value = getattr(invoice, field_name)
        if value is None:
            continue
        references = invoice.evidence.get(field_name, ())
        if _has_valid_evidence(references):
            continue
        findings.append(
            VerificationFinding(
                finding_type="ungrounded_extracted_field",
                severity="medium",
                explanation=(
                    f"Extracted field '{field_name}' lacks valid page or OCR evidence."
                ),
                comparison_source="invoice_fields",
                deterministic_rule=(
                    f"invoice.evidence['{field_name}'] must contain a valid EvidenceReference"
                ),
                observed_value=str(value),
                expected_value="valid EvidenceReference",
                details={
                    "field": field_name,
                    "reason": _grounding_reason(references),
                },
            )
        )

    for index, item in enumerate(invoice.line_items):
        if _has_valid_evidence(item.evidence):
            continue
        findings.append(
            VerificationFinding(
                finding_type="ungrounded_extracted_field",
                severity="medium",
                explanation=(
                    f"Extracted line item {index} lacks valid page or OCR evidence."
                ),
                comparison_source="invoice_line_items",
                deterministic_rule=(
                    "line_item.evidence must contain a valid EvidenceReference"
                ),
                observed_value=item.description or item.product_identifier,
                expected_value="valid EvidenceReference",
                details={
                    "field": f"line_items[{index}]",
                    "line_item_index": index,
                    "reason": _grounding_reason(item.evidence),
                },
            )
        )

    return findings


__all__ = [
    "REQUIRED_GROUNDED_HEADER_FIELDS",
    "check_evidence_grounding",
]
