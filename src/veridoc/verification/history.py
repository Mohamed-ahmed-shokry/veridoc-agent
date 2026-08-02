"""Deterministic statistical comparisons against vendor invoice history."""

from __future__ import annotations

from decimal import Decimal, localcontext

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.models import VerificationFinding
from veridoc.verification.references import HistoricalInvoice

MINIMUM_HISTORY_SAMPLE_SIZE = 3
OUTLIER_Z_SCORE = Decimal(3)


def check_historical_total(
    invoice: InvoiceExtraction, history: list[HistoricalInvoice]
) -> list[VerificationFinding]:
    """Compare an invoice total with same-currency historical invoice totals."""
    if invoice.total is None:
        return []

    values = [
        historical_invoice.total
        for historical_invoice in history
        if historical_invoice.total is not None
        and historical_invoice.currency == invoice.currency
    ]
    if len(values) < MINIMUM_HISTORY_SAMPLE_SIZE:
        return [_insufficient_history_finding(invoice, len(values))]

    mean = sum(values, start=Decimal(0)) / len(values)
    standard_deviation = _population_standard_deviation(values, mean)
    if standard_deviation == 0:
        return _check_zero_variance_total(invoice, mean, len(values))

    z_score = abs(invoice.total - mean) / standard_deviation
    if z_score < OUTLIER_Z_SCORE:
        return []
    lower_bound = mean - (OUTLIER_Z_SCORE * standard_deviation)
    upper_bound = mean + (OUTLIER_Z_SCORE * standard_deviation)
    return [
        VerificationFinding(
            finding_type="historical_total_outlier",
            severity="high",
            explanation="The invoice total is outside the vendor's established range.",
            comparison_source="vendor_history",
            deterministic_rule="absolute_z_score >= 3",
            observed_value=str(invoice.total),
            expected_range=(str(lower_bound), str(upper_bound)),
            historical_sample_size=len(values),
            historical_mean=mean,
            historical_standard_deviation=standard_deviation,
            z_score=z_score,
            details={"currency": invoice.currency},
        )
    ]


def _check_zero_variance_total(
    invoice: InvoiceExtraction, mean: Decimal, sample_size: int
) -> list[VerificationFinding]:
    if invoice.total == mean:
        return []
    return [
        VerificationFinding(
            finding_type="historical_total_outlier",
            severity="high",
            explanation="The invoice total differs from a uniform vendor history.",
            comparison_source="vendor_history",
            deterministic_rule="standard_deviation == 0 and total != mean",
            observed_value=str(invoice.total),
            expected_value=str(mean),
            historical_sample_size=sample_size,
            historical_mean=mean,
            historical_standard_deviation=Decimal(0),
            details={"currency": invoice.currency},
        )
    ]


def _insufficient_history_finding(
    invoice: InvoiceExtraction, sample_size: int
) -> VerificationFinding:
    return VerificationFinding(
        finding_type="insufficient_history",
        severity="info",
        explanation="There are not enough same-currency invoice totals for a reliable comparison.",
        comparison_source="vendor_history",
        deterministic_rule=f"sample_size >= {MINIMUM_HISTORY_SAMPLE_SIZE}",
        observed_value=str(invoice.total),
        historical_sample_size=sample_size,
        details={
            "metric": "invoice_total",
            "currency": invoice.currency,
            "required_sample_size": MINIMUM_HISTORY_SAMPLE_SIZE,
        },
    )


def _population_standard_deviation(values: list[Decimal], mean: Decimal) -> Decimal:
    variance = sum(((value - mean) ** 2 for value in values), start=Decimal(0)) / len(
        values
    )
    with localcontext() as context:
        context.prec = 28
        return variance.sqrt()
