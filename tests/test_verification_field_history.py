"""Historically consistent field checks using synthetic vendor facts."""

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.field_history import (
    check_historical_currency,
    check_payment_terms,
)
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


def _currency_history(*currencies: str | None) -> list[HistoricalInvoice]:
    return [
        HistoricalInvoice(
            vendor_key="fictional-supplies",
            invoice_number=f"INV-{index}",
            currency=currency,
        )
        for index, currency in enumerate(currencies, start=1)
    ]


def test_historical_currency_accepts_consistent_and_ignores_sparse_or_mixed() -> None:
    usd_invoice = InvoiceExtraction(document_type="invoice", currency="USD")
    no_currency_invoice = InvoiceExtraction(document_type="invoice", currency=None)

    assert (
        check_historical_currency(
            no_currency_invoice, _currency_history("USD", "USD", "USD")
        )
        == []
    )
    assert check_historical_currency(usd_invoice, _currency_history("USD", "USD")) == []
    assert (
        check_historical_currency(usd_invoice, _currency_history("USD", "USD", "EUR"))
        == []
    )
    assert (
        check_historical_currency(usd_invoice, _currency_history("USD", "USD", "USD"))
        == []
    )
    unvalidated_history = [
        HistoricalInvoice.model_construct(
            vendor_key="fictional-supplies",
            invoice_number="INV-1",
            currency=" usd ",
        ),
        *_currency_history("USD", "USD"),
    ]
    assert check_historical_currency(usd_invoice, unvalidated_history) == []


def test_historical_currency_flags_mismatch_against_consistent_history() -> None:
    invoice = InvoiceExtraction(document_type="invoice", currency="EUR")
    history = _currency_history("USD", "USD", "USD", None)
    snapshot = invoice.model_copy(deep=True)

    findings = check_historical_currency(invoice, history)

    assert invoice == snapshot
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "historical_currency_mismatch"
    assert finding.severity == "medium"
    assert finding.comparison_source == "vendor_history"
    assert finding.observed_value == "EUR"
    assert finding.expected_value == "USD"
    assert finding.historical_sample_size == 3
    assert finding.details == {
        "field": "currency",
        "observed_currency": "EUR",
        "expected_currency": "USD",
    }


def test_verification_service_routes_historical_currency_mismatch_to_review() -> None:
    from datetime import date
    from decimal import Decimal

    from veridoc.processing.verdict import derive_verdict
    from veridoc.verification.service import VerificationService

    class _CurrencyHistoryRepo:
        def list_vendor_invoices(self, vendor_key: str) -> list[HistoricalInvoice]:
            return _currency_history("USD", "USD", "USD")

        def get_purchase_order(self, vendor_key: str, po_number: str) -> object | None:
            return None

    service = VerificationService(repository=_CurrencyHistoryRepo())  # type: ignore[arg-type]
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies",
        invoice_number="INV-900",
        invoice_date=date(2026, 11, 20),
        currency="EUR",
        total=Decimal("100.00"),
    )
    result = service.verify(invoice, reference_date=date(2026, 11, 22))
    assert any(
        f.finding_type == "historical_currency_mismatch" for f in result.findings
    )
    assert derive_verdict(result).status == "review_required"
