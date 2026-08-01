"""Historical total comparison tests with synthetic vendor records."""

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.history import check_historical_total
from veridoc.verification.references import HistoricalInvoice


def _history(*totals: str) -> list[HistoricalInvoice]:
    return [
        HistoricalInvoice(
            vendor_key="fictional-supplies",
            invoice_number=f"INV-{index}",
            currency="USD",
            total=total,
        )
        for index, total in enumerate(totals, start=1)
    ]


def test_historical_total_check_accepts_a_value_inside_the_established_range() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice", currency="USD", total="7300.00"
    )

    assert (
        check_historical_total(invoice, _history("7000.00", "7200.00", "7400.00")) == []
    )


def test_historical_total_check_reports_an_outlier_with_statistics() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice", currency="USD", total="18400.00"
    )

    findings = check_historical_total(
        invoice, _history("7000.00", "7200.00", "7400.00")
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "historical_total_outlier"
    assert finding.historical_sample_size == 3
    assert finding.historical_mean == 7200
    assert finding.historical_standard_deviation is not None
    assert finding.z_score is not None and finding.z_score > 3


def test_historical_total_check_declares_insufficient_same_currency_history() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice", currency="USD", total="7200.00"
    )
    history = _history("7000.00") + [
        HistoricalInvoice(
            vendor_key="fictional-supplies",
            invoice_number="INV-EUR",
            currency="EUR",
            total="7000.00",
        )
    ]

    findings = check_historical_total(invoice, history)

    assert len(findings) == 1
    assert findings[0].finding_type == "insufficient_history"
    assert findings[0].historical_sample_size == 1
    assert findings[0].details["metric"] == "invoice_total"
