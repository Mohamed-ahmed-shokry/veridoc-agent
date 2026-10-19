"""Deterministic extraction uncertainty verification for extracted invoices.

In Veridoc's document-intelligence pipeline, extraction transforms OCR text and
page images into structured invoice models. The extraction boundary prompts models
to report any perceptual or textual ambiguities into ``uncertainties``:
"If a field is not present or cannot be determined with certainty, leave it null or
unknown. Record ambiguities in uncertainties."

When an extraction contains declared uncertainties—such as watermarks obscuring
monetary totals, damaged or torn dates, ambiguous handwriting, or unreadable tax
values—the extracted data cannot be accepted as ground truth without human inspection.

Allowing invoices with declared extraction uncertainties to clear automated processing
creates a grave audit risk and subverts Veridoc's purpose of deciding whether
extracted data can be trusted.

Establishing an explicit, deterministic check ensures that every declared uncertainty
in ``invoice.uncertainties`` produces a structured ``extraction_uncertainty`` finding
with ``severity="medium"``, routing the invoice to mandatory human review.
"""

from __future__ import annotations

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.models import VerificationFinding


def check_extraction_uncertainties(
    invoice: InvoiceExtraction,
) -> list[VerificationFinding]:
    """Flag invoices with declared extraction uncertainties or ambiguities.

    Returns an empty list when:
    - ``not invoice.uncertainties`` (no declared uncertainties).

    Returns a list of ``extraction_uncertainty`` findings (severity="medium"),
    one for each uncertainty in ``invoice.uncertainties``, preserving order.
    """
    if not invoice.uncertainties:
        return []

    findings: list[VerificationFinding] = []
    for index, uncertainty in enumerate(invoice.uncertainties):
        field_name = uncertainty.field
        reason = uncertainty.reason

        if field_name:
            explanation = (
                f"Extraction uncertainty declared for field '{field_name}': {reason}"
            )
        else:
            explanation = f"General extraction uncertainty declared: {reason}"

        findings.append(
            VerificationFinding(
                finding_type="extraction_uncertainty",
                severity="medium",
                explanation=explanation,
                comparison_source="invoice_fields",
                deterministic_rule="len(invoice.uncertainties) == 0",
                observed_value=reason,
                expected_value=None,
                details={
                    "field": field_name,
                    "reason": reason,
                    "uncertainty_index": index,
                },
            )
        )

    return findings


__all__ = ["check_extraction_uncertainties"]
