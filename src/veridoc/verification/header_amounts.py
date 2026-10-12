"""Deterministic invoice header monetary bound checks.

In commercial accounts payable and document intelligence, an invoice header
specifies three pre-total monetary components: subtotal, tax, and discount.
Under standard accounting principles (GAAP, IFRS) and tax compliance rules
(VAT, GST, sales tax), each component must satisfy strict sign and relative
magnitude invariants:

1. ``subtotal > 0``: The pre-tax, pre-discount subtotal must be strictly
   positive when present. A negative subtotal (< 0) indicates a credit memo,
   billing reversal, or OCR minus-sign defect (high severity); a zero subtotal
   (== 0) indicates a pro-forma voucher, tax-only adjustment, or OCR extraction
   dropout (medium severity).
2. ``tax >= 0``: While zero tax (0.00) is valid for tax-exempt, zero-rated,
   reverse-charge, or export invoices, a commercial invoice cannot specify a
   negative tax liability (< 0). Negative tax amounts indicate unauthorized
   embedded tax credits, withholding-tax confusion, or OCR minus-sign defects
   (high severity).
3. ``0 <= discount <= subtotal``: In Veridoc's canonical formula
   (``subtotal + tax - discount == total``), ``discount`` is a non-negative
   deduction magnitude. A negative discount (< 0) mathematically adds to the
   payable total as an unauthorized surcharge or reflects an unnormalized sign
   from a printed ``-10.00`` discount line (high severity). Furthermore, when
   ``subtotal > 0``, a discount exceeding the subtotal (``discount > subtotal``)
   yields a negative net pre-tax base (``subtotal - discount < 0``), indicating
   an embedded rebate offset or OCR column transposition (high severity).
"""

from __future__ import annotations

from decimal import Decimal

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.models import FindingSeverity, VerificationFinding


def check_non_positive_subtotal(
    invoice: InvoiceExtraction,
) -> list[VerificationFinding]:
    """Return a finding when the invoice subtotal is zero or negative.

    Args:
        invoice: The structured invoice extraction to check.

    Returns:
        A list containing one ``non_positive_subtotal`` finding if
        ``invoice.subtotal`` is present and non-positive (<= 0), or an empty
        list otherwise. Negative subtotals produce ``high`` severity findings;
        zero subtotals produce ``medium`` severity findings.
    """
    if invoice.subtotal is None:
        return []

    if invoice.subtotal > Decimal(0):
        return []

    is_negative = invoice.subtotal < Decimal(0)
    severity: FindingSeverity = "high" if is_negative else "medium"

    if is_negative:
        explanation = (
            f"The invoice subtotal is negative ({invoice.subtotal}). Negative "
            "subtotals indicate credit notes, billing reversals, or extraction "
            "errors requiring review."
        )
    else:
        explanation = (
            "The invoice subtotal is zero (0.00). Zero subtotals indicate "
            "pro-forma documents, zero-value vouchers, or extraction errors "
            "requiring review."
        )

    details: dict[str, str | int | float | bool | None] = {
        "field": "subtotal",
        "subtotal": str(invoice.subtotal),
        "is_zero": not is_negative,
        "is_negative": is_negative,
    }
    if invoice.currency is not None:
        details["currency"] = invoice.currency

    return [
        VerificationFinding(
            finding_type="non_positive_subtotal",
            severity=severity,
            explanation=explanation,
            comparison_source="invoice_fields",
            deterministic_rule="invoice.subtotal > 0",
            observed_value=str(invoice.subtotal),
            expected_value="> 0.00",
            details=details,
        )
    ]


def check_negative_tax(
    invoice: InvoiceExtraction,
) -> list[VerificationFinding]:
    """Return a finding when the invoice tax amount is strictly negative.

    Args:
        invoice: The structured invoice extraction to check.

    Returns:
        A list containing one ``high``-severity ``negative_tax`` finding if
        ``invoice.tax`` is present and strictly negative (< 0), or an empty
        list otherwise. Zero tax (0.00) is valid for tax-exempt, zero-rated,
        reverse-charge, or export invoices.
    """
    if invoice.tax is None:
        return []

    if invoice.tax >= Decimal(0):
        return []

    explanation = (
        f"The invoice tax amount is negative ({invoice.tax}). Negative tax "
        "amounts indicate unauthorized tax credits, withholding-tax "
        "misclassifications, or extraction errors requiring review."
    )

    details: dict[str, str | int | float | bool | None] = {
        "field": "tax",
        "tax": str(invoice.tax),
        "is_negative": True,
    }
    if invoice.currency is not None:
        details["currency"] = invoice.currency

    return [
        VerificationFinding(
            finding_type="negative_tax",
            severity="high",
            explanation=explanation,
            comparison_source="invoice_fields",
            deterministic_rule="invoice.tax >= 0",
            observed_value=str(invoice.tax),
            expected_value=">= 0.00",
            details=details,
        )
    ]


def check_invalid_discount(
    invoice: InvoiceExtraction,
) -> list[VerificationFinding]:
    """Return a finding when the invoice discount is negative.

    Args:
        invoice: The structured invoice extraction to check.

    Returns:
        A list containing one ``high``-severity ``invalid_discount`` finding if
        ``invoice.discount`` is present and strictly negative (< 0), or an empty
        list otherwise. Zero discount (0.00) is valid.
    """
    if invoice.discount is None:
        return []

    if invoice.discount < Decimal(0):
        explanation = (
            f"The invoice discount amount is negative ({invoice.discount}). "
            "In the canonical invoice equation (subtotal + tax - discount == total), "
            "a negative discount increases the payable total as an unauthorized "
            "surcharge or indicates a sign extraction error requiring review."
        )
        details: dict[str, str | int | float | bool | None] = {
            "field": "discount",
            "discount": str(invoice.discount),
            "reason": "negative_discount",
            "is_negative": True,
        }
        if invoice.currency is not None:
            details["currency"] = invoice.currency

        return [
            VerificationFinding(
                finding_type="invalid_discount",
                severity="high",
                explanation=explanation,
                comparison_source="invoice_fields",
                deterministic_rule="invoice.discount >= 0",
                observed_value=str(invoice.discount),
                expected_value=">= 0.00",
                details=details,
            )
        ]

    return []
