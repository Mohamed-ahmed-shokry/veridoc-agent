"""Historically consistent field checks using synthetic vendor facts."""

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.field_history import check_payment_terms
from veridoc.verification.references import HistoricalInvoice


def _history(*payment_terms: str) -> list[HistoricalInvoice]:
    return [
        HistoricalInvoice(
            vendor_key="fictional-supplies",
            invoice_number=f"INV-{index}",
            currency="USD",
            payment_terms=payment_term,
        )
        for index, payment_term in enumerate(payment_terms, start=1)
    ]


def test_payment_terms_check_accepts_the_consistent_historical_value() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice", currency="USD", payment_terms="Net 30"
    )

    assert check_payment_terms(invoice, _history("Net 30", "Net 30", "Net 30")) == []


def test_payment_terms_check_reports_changed_and_missing_values() -> None:
    history = _history("Net 30", "Net 30", "Net 30")
    changed_invoice = InvoiceExtraction(
        document_type="invoice", currency="USD", payment_terms="Due on receipt"
    )
    missing_invoice = InvoiceExtraction(document_type="invoice", currency="USD")

    changed = check_payment_terms(changed_invoice, history)
    missing = check_payment_terms(missing_invoice, history)

    assert changed[0].finding_type == "payment_terms_changed"
    assert changed[0].expected_value == "Net 30"
    assert missing[0].finding_type == "missing_historical_field"
    assert missing[0].details == {"field": "payment_terms"}


def test_payment_terms_check_declares_insufficient_history() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice", currency="USD", payment_terms="Net 30"
    )

    findings = check_payment_terms(invoice, _history("Net 30"))

    assert [finding.finding_type for finding in findings] == ["insufficient_history"]
    assert findings[0].historical_sample_size == 1
