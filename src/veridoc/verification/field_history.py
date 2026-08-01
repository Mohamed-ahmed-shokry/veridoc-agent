"""Checks for historically consistent invoice fields."""

from __future__ import annotations

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
