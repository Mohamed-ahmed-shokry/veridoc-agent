"""Deterministic non-positive invoice total check.

In commercial accounts payable and document intelligence, an invoice
(document_type="invoice") is an instrument requesting payment for goods or
services delivered. Under standard accounting principles (GAAP, IFRS) and
business controls, a commercial invoice must specify a strictly positive payable
total (total > 0).

An invoice specifying a zero total (0.00) indicates an operational anomaly:
an informational zero-value delivery slip, pro-forma quote, warranty replacement,
or sample receipt erroneously routed as a commercial invoice, or an OCR/vision
extraction defect where the monetary total was blanked or parsed as zero.
Allowing zero-dollar invoices to pass automatically can cause unfulfilled
purchase orders to be marked as fulfilled or introduce zero-value vouchers into
accounting ledgers.

An invoice specifying a negative total (< 0) indicates a credit note, debit
memo, return adjustment, or refund claim. Processing a negative amount under a
standard invoice workflow without credit-note authorization corrupts accounts
payable ledgers and creates risk of unauthorized payment reversals.

This check detects non-positive invoice totals, assigning high severity to
negative totals and medium severity to zero totals.
"""

from __future__ import annotations

from decimal import Decimal

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.models import FindingSeverity, VerificationFinding


def check_non_positive_invoice_total(
    invoice: InvoiceExtraction,
) -> list[VerificationFinding]:
    """Return a finding when the invoice total is zero or negative.

    Args:
        invoice: The structured invoice extraction to check.

    Returns:
        A list containing one ``non_positive_invoice_total`` finding if the
        invoice total is present and non-positive (<= 0), or an empty list
        otherwise. Negative totals produce ``high`` severity findings;
        zero totals produce ``medium`` severity findings.
    """
    if invoice.total is None:
        return []

    if invoice.total > Decimal(0):
        return []

    is_negative = invoice.total < Decimal(0)
    severity: FindingSeverity = "high" if is_negative else "medium"

    if is_negative:
        explanation = (
            f"The invoice total is negative ({invoice.total}). Negative totals "
            "indicate credit notes, refunds, or billing reversals requiring "
            "review."
        )
    else:
        explanation = (
            "The invoice total is zero (0.00). Zero-amount invoices indicate "
            "pro-forma documents, zero-value vouchers, or extraction errors "
            "requiring review."
        )

    details: dict[str, str | int | float | bool | None] = {
        "field": "total",
        "total": str(invoice.total),
        "is_zero": not is_negative,
        "is_negative": is_negative,
    }
    if invoice.currency is not None:
        details["currency"] = invoice.currency

    return [
        VerificationFinding(
            finding_type="non_positive_invoice_total",
            severity=severity,
            explanation=explanation,
            comparison_source="invoice_fields",
            deterministic_rule="invoice.total > 0",
            observed_value=str(invoice.total),
            expected_value="> 0.00",
            details=details,
        )
    ]
