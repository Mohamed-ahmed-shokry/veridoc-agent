"""Checks for historically consistent invoice fields."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from typing import Final

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.history import MINIMUM_HISTORY_SAMPLE_SIZE
from veridoc.verification.models import VerificationFinding
from veridoc.verification.references import HistoricalInvoice


def check_payment_terms(
    invoice: InvoiceExtraction, history: list[HistoricalInvoice]
) -> list[VerificationFinding]:
    """Report changed or missing payment terms when history is consistent."""
    historical_terms = [
        historical_invoice.payment_terms
        for historical_invoice in history
        if historical_invoice.currency == invoice.currency
        and historical_invoice.payment_terms is not None
    ]
    if len(historical_terms) < MINIMUM_HISTORY_SAMPLE_SIZE:
        return _insufficient_history(invoice, len(historical_terms))
    if len(set(historical_terms)) != 1:
        return []

    expected_terms = historical_terms[0]
    if invoice.payment_terms is None:
        return [
            VerificationFinding(
                finding_type="missing_historical_field",
                severity="low",
                explanation="Payment terms are absent despite a consistent vendor history.",
                comparison_source="vendor_history",
                deterministic_rule="historically_consistent_payment_terms must be present",
                expected_value=expected_terms,
                historical_sample_size=len(historical_terms),
                details={"field": "payment_terms"},
            )
        ]
    if invoice.payment_terms == expected_terms:
        return []
    return [
        VerificationFinding(
            finding_type="payment_terms_changed",
            severity="medium",
            explanation="Payment terms differ from the vendor's consistent history.",
            comparison_source="vendor_history",
            deterministic_rule="payment_terms == historical_consistent_value",
            observed_value=invoice.payment_terms,
            expected_value=expected_terms,
            historical_sample_size=len(historical_terms),
            details={"field": "payment_terms"},
        )
    ]


def _insufficient_history(
    invoice: InvoiceExtraction, sample_size: int
) -> list[VerificationFinding]:
    if invoice.payment_terms is None:
        return []
    return [
        VerificationFinding(
            finding_type="insufficient_history",
            severity="info",
            explanation="There are not enough payment-term observations for a reliable comparison.",
            comparison_source="vendor_history",
            deterministic_rule=f"sample_size >= {MINIMUM_HISTORY_SAMPLE_SIZE}",
            observed_value=invoice.payment_terms,
            historical_sample_size=sample_size,
            details={
                "metric": "payment_terms",
                "required_sample_size": MINIMUM_HISTORY_SAMPLE_SIZE,
            },
        )
    ]


def check_historical_currency(
    invoice: InvoiceExtraction, history: Sequence[HistoricalInvoice]
) -> list[VerificationFinding]:
    """Flag invoices whose currency diverges from a vendor's consistent history."""
    if invoice.currency is None or not invoice.currency.strip():
        return []

    historical_currencies = [
        historical_invoice.currency.strip().upper()
        for historical_invoice in history
        if historical_invoice.currency is not None
        and historical_invoice.currency.strip()
    ]
    if len(historical_currencies) < MINIMUM_HISTORY_SAMPLE_SIZE:
        return []
    if len(set(historical_currencies)) != 1:
        return []

    expected_currency = historical_currencies[0]
    observed_currency = invoice.currency.strip().upper()
    if observed_currency == expected_currency:
        return []

    return [
        VerificationFinding(
            finding_type="historical_currency_mismatch",
            severity="medium",
            explanation=(
                f"Invoice currency '{observed_currency}' differs from the vendor's "
                f"consistent historical invoicing currency '{expected_currency}'."
            ),
            comparison_source="vendor_history",
            deterministic_rule="currency == historical_consistent_currency",
            observed_value=observed_currency,
            expected_value=expected_currency,
            historical_sample_size=len(historical_currencies),
            details={
                "field": "currency",
                "observed_currency": observed_currency,
                "expected_currency": expected_currency,
            },
        )
    ]


TAX_RATE_TOLERANCE: Final[Decimal] = Decimal("0.005")
TAX_RATE_PRECISION: Final[Decimal] = Decimal("0.0001")
_PERCENT_PRECISION: Final[Decimal] = Decimal("0.01")


def _derive_tax_rate(
    subtotal: Decimal | None,
    tax: Decimal | None,
) -> Decimal | None:
    if subtotal is None or tax is None or subtotal <= Decimal(0) or tax < Decimal(0):
        return None
    try:
        return (tax / subtotal).quantize(TAX_RATE_PRECISION)
    except (InvalidOperation, ZeroDivisionError):
        return None


def _format_rate_percent(rate: Decimal) -> str:
    return f"{(rate * Decimal(100)).quantize(_PERCENT_PRECISION)}%"


def check_historical_tax_rate(
    invoice: InvoiceExtraction,
    history: Sequence[HistoricalInvoice],
    *,
    tolerance: Decimal = TAX_RATE_TOLERANCE,
) -> list[VerificationFinding]:
    """Flag invoices whose effective tax rate shifts from consistent history."""
    if tolerance < Decimal(0):
        raise ValueError("tolerance must be non-negative.")
    if invoice.currency is None:
        return []

    observed_rate = _derive_tax_rate(invoice.subtotal, invoice.tax)
    if observed_rate is None:
        return []

    historical_rates: list[Decimal] = []
    for historical_invoice in history:
        if historical_invoice.currency != invoice.currency:
            continue
        rate = _derive_tax_rate(historical_invoice.subtotal, historical_invoice.tax)
        if rate is not None:
            historical_rates.append(rate)

    if len(historical_rates) < MINIMUM_HISTORY_SAMPLE_SIZE:
        return []

    if max(historical_rates) - min(historical_rates) > tolerance:
        return []

    expected_rate = (
        sum(historical_rates, start=Decimal(0)) / len(historical_rates)
    ).quantize(TAX_RATE_PRECISION)
    if abs(observed_rate - expected_rate) <= tolerance:
        return []

    observed_pct = _format_rate_percent(observed_rate)
    expected_pct = _format_rate_percent(expected_rate)
    return [
        VerificationFinding(
            finding_type="historical_tax_rate_mismatch",
            severity="medium",
            explanation=(
                f"Effective tax rate {observed_pct} differs from the vendor's "
                f"consistent historical tax rate {expected_pct}."
            ),
            comparison_source="vendor_history",
            deterministic_rule=f"abs(tax / subtotal - historical_tax_rate) <= {tolerance}",
            observed_value=observed_pct,
            expected_value=expected_pct,
            historical_sample_size=len(historical_rates),
            details={
                "field": "tax",
                "currency": invoice.currency,
                "observed_tax_rate": str(observed_rate),
                "expected_tax_rate": str(expected_rate),
                "tolerance": str(tolerance),
            },
        )
    ]
