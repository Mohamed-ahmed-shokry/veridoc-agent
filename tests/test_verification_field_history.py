"""Historically consistent field checks using synthetic vendor facts."""

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.field_history import (
    check_historical_currency,
    check_historical_tax_rate,
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


def _tax_history(*pairs: tuple[str, str]) -> list[HistoricalInvoice]:
    from decimal import Decimal

    return [
        HistoricalInvoice(
            vendor_key="fictional-supplies",
            invoice_number=f"INV-{index}",
            currency="GBP",
            subtotal=Decimal(subtotal),
            tax=Decimal(tax),
        )
        for index, (subtotal, tax) in enumerate(pairs, start=1)
    ]


def test_historical_tax_rate_exclusions_and_tolerance() -> None:
    from decimal import Decimal

    import pytest

    history = _tax_history(
        ("100.00", "20.00"), ("200.00", "40.00"), ("150.00", "30.00")
    )

    # Missing currency, subtotal, or tax, or non-positive subtotal
    assert (
        check_historical_tax_rate(
            InvoiceExtraction(
                document_type="invoice",
                currency=None,
                subtotal=Decimal("100.00"),
                tax=Decimal("20.00"),
            ),
            history,
        )
        == []
    )
    assert (
        check_historical_tax_rate(
            InvoiceExtraction(
                document_type="invoice",
                currency="GBP",
                subtotal=Decimal("0.00"),
                tax=Decimal("0.00"),
            ),
            history,
        )
        == []
    )
    # Sparse history (< 3)
    assert (
        check_historical_tax_rate(
            InvoiceExtraction(
                document_type="invoice",
                currency="GBP",
                subtotal=Decimal("100.00"),
                tax=Decimal("0.00"),
            ),
            history[:2],
        )
        == []
    )
    # Mixed-rate history
    mixed_history = _tax_history(
        ("100.00", "10.00"), ("100.00", "20.00"), ("100.00", "20.00")
    )
    assert (
        check_historical_tax_rate(
            InvoiceExtraction(
                document_type="invoice",
                currency="GBP",
                subtotal=Decimal("100.00"),
                tax=Decimal("15.00"),
            ),
            mixed_history,
        )
        == []
    )
    # Within default tolerance (0.2040 vs 0.2000 <= 0.005)
    assert (
        check_historical_tax_rate(
            InvoiceExtraction(
                document_type="invoice",
                currency="GBP",
                subtotal=Decimal("100.00"),
                tax=Decimal("20.40"),
            ),
            history,
        )
        == []
    )
    with pytest.raises(ValueError, match="tolerance"):
        check_historical_tax_rate(
            InvoiceExtraction(document_type="invoice", currency="GBP"),
            history,
            tolerance=Decimal("-0.01"),
        )


def test_historical_tax_rate_flags_shift_and_preserves_immutability() -> None:
    from decimal import Decimal

    history = _tax_history(
        ("100.00", "20.00"), ("200.00", "40.00"), ("150.00", "30.00")
    )
    invoice = InvoiceExtraction(
        document_type="invoice",
        currency="GBP",
        subtotal=Decimal("100.00"),
        tax=Decimal("0.00"),
    )
    snapshot = invoice.model_copy(deep=True)
    findings = check_historical_tax_rate(invoice, history)

    assert invoice == snapshot
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "historical_tax_rate_mismatch"
    assert finding.severity == "medium"
    assert finding.comparison_source == "vendor_history"
    assert finding.observed_value == "0.00%"
    assert finding.expected_value == "20.00%"
    assert finding.historical_sample_size == 3
    assert finding.details == {
        "field": "tax",
        "currency": "GBP",
        "observed_tax_rate": "0.0000",
        "expected_tax_rate": "0.2000",
        "tolerance": "0.005",
    }


def test_verification_service_routes_historical_tax_rate_mismatch_to_review() -> None:
    from datetime import date
    from decimal import Decimal

    from veridoc.processing.verdict import derive_verdict
    from veridoc.verification.service import VerificationService

    class _TaxHistoryRepo:
        def list_vendor_invoices(self, vendor_key: str) -> list[HistoricalInvoice]:
            return _tax_history(
                ("100.00", "20.00"), ("200.00", "40.00"), ("150.00", "30.00")
            )

        def get_purchase_order(self, vendor_key: str, po_number: str) -> object | None:
            return None

    service = VerificationService(repository=_TaxHistoryRepo())  # type: ignore[arg-type]
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies",
        invoice_number="INV-901",
        invoice_date=date(2026, 11, 20),
        currency="GBP",
        subtotal=Decimal("100.00"),
        tax=Decimal("5.00"),
        total=Decimal("105.00"),
    )
    result = service.verify(invoice, reference_date=date(2026, 11, 23))
    assert any(
        f.finding_type == "historical_tax_rate_mismatch" for f in result.findings
    )
    assert derive_verdict(result).status == "review_required"
