"""Deterministic excessive tax amount verification for invoice headers.

In commercial accounts payable (AP) operations and tax compliance (VAT, GST, sales tax),
statutory tax liabilities are levied as a strictly bounded percentage of the taxable supply
(``subtotal``). Standard statutory tax rates across global tax authorities range from 0%
(zero-rated, exempt, or reverse-charge supplies) up to a maximum standard rate of approximately
27% (the highest standard VAT rate among OECD nations, in Hungary).

While Phase 26 establishes that tax amounts must be non-negative (``tax >= 0``), an invoice
specifying a positive tax amount exceeding the pre-tax subtotal (``tax > subtotal`` when
``subtotal > 0``), or exceeding the payable invoice total (``tax > total`` when ``subtotal``
is omitted and ``total > 0``), violates commercial tax invariants:
1. An effective tax rate exceeding 100% of the taxable base is unlawful on commercial B2B invoices
   and almost invariably indicates vision/OCR decimal transposition (e.g. $150.00 tax misread
   on a $100.00 subtotal instead of $15.00).
2. Tax is an additive component of the payable total (``subtotal + tax - discount == total``).
   A tax amount greater than the payable total demonstrates field transposition between tax and
   total, or unauthorized surcharges.

This module flags excessive tax amounts with ``high`` severity, routing invoices to mandatory
human review before financial disbursement.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.models import VerificationFinding

DEFAULT_MAX_TAX_TO_SUBTOTAL_RATIO: Final[Decimal] = Decimal("1.00")


def check_excessive_tax(
    invoice: InvoiceExtraction,
    max_tax_rate: Decimal = DEFAULT_MAX_TAX_TO_SUBTOTAL_RATIO,
) -> list[VerificationFinding]:
    """Flag invoices whose tax amount exceeds the pre-tax subtotal or total.

    Args:
        invoice: The extracted invoice data to verify.
        max_tax_rate: The maximum permitted ratio of tax to pre-tax subtotal.
            Defaults to ``1.00`` (100% of subtotal).

    Returns:
        A list containing one ``excessive_tax`` finding (severity="high") if
        ``tax`` exceeds ``subtotal * max_tax_rate`` (when ``subtotal > 0``), or
        if ``tax`` exceeds ``total`` (when ``subtotal`` is absent and ``total > 0``).
        Returns an empty list otherwise.
    """
    tax = invoice.tax
    if tax is None or tax <= Decimal(0):
        return []

    subtotal = invoice.subtotal
    if subtotal is not None:
        if subtotal <= Decimal(0):
            return []

        max_allowed_tax = subtotal * max_tax_rate
        if tax > max_allowed_tax:
            effective_rate = tax / subtotal
            effective_rate_pct = float(effective_rate * 100)
            max_rate_pct = float(max_tax_rate * 100)
            explanation = (
                f"The invoice tax ({tax}) exceeds the pre-tax subtotal ({subtotal}) "
                f"at an effective rate of {effective_rate_pct:.1f}% (maximum allowed: {max_rate_pct:.1f}%). "
                "Tax amounts exceeding the taxable base indicate OCR decimal misreads, field transposition, "
                "or fictitious tax liabilities requiring review."
            )
            rule = (
                "invoice.tax <= invoice.subtotal"
                if max_tax_rate == DEFAULT_MAX_TAX_TO_SUBTOTAL_RATIO
                else f"invoice.tax <= invoice.subtotal * {max_tax_rate}"
            )
            expected_val = (
                f"<= {subtotal}"
                if max_tax_rate == DEFAULT_MAX_TAX_TO_SUBTOTAL_RATIO
                else f"<= {max_allowed_tax}"
            )
            details: dict[str, str | int | float | bool | None] = {
                "field": "tax",
                "tax": str(tax),
                "subtotal": str(subtotal),
                "effective_tax_rate": f"{effective_rate:.4f}",
                "max_tax_rate": str(max_tax_rate),
            }
            if invoice.currency is not None:
                details["currency"] = invoice.currency

            return [
                VerificationFinding(
                    finding_type="excessive_tax",
                    severity="high",
                    explanation=explanation,
                    comparison_source="invoice_fields",
                    deterministic_rule=rule,
                    observed_value=str(tax),
                    expected_value=expected_val,
                    details=details,
                )
            ]
        return []

    total = invoice.total
    if total is not None:
        if total <= Decimal(0):
            return []

        if tax > total:
            explanation = (
                f"The invoice tax ({tax}) exceeds the payable invoice total ({total}). "
                "Tax is a component of the invoice total and cannot exceed the total payable amount, "
                "indicating OCR field transposition or calculation distortion requiring review."
            )
            details = {
                "field": "tax",
                "tax": str(tax),
                "total": str(total),
            }
            if invoice.currency is not None:
                details["currency"] = invoice.currency

            return [
                VerificationFinding(
                    finding_type="excessive_tax",
                    severity="high",
                    explanation=explanation,
                    comparison_source="invoice_fields",
                    deterministic_rule="invoice.tax <= invoice.total",
                    observed_value=str(tax),
                    expected_value=f"<= {total}",
                    details=details,
                )
            ]

    return []


__all__ = [
    "DEFAULT_MAX_TAX_TO_SUBTOTAL_RATIO",
    "check_excessive_tax",
]
