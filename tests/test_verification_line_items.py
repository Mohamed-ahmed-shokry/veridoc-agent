"""Vendor-history line-item occurrence tests with synthetic data."""

from veridoc.extraction.models import InvoiceExtraction, InvoiceLineItem
from veridoc.verification.line_items import check_line_item_occurrence, line_item_key
from veridoc.verification.references import HistoricalInvoice, ReferenceLineItem


def _history(*product_identifiers: str) -> list[HistoricalInvoice]:
    return [
        HistoricalInvoice(
            vendor_key="fictional-supplies",
            invoice_number=f"INV-{index}",
            currency="USD",
            line_items=[ReferenceLineItem(product_identifier=product_identifier)],
        )
        for index, product_identifier in enumerate(product_identifiers, start=1)
    ]


def test_line_item_occurrence_accepts_common_items_and_normalizes_keys() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        currency="USD",
        line_items=[InvoiceLineItem(product_identifier=" consulting ")],
    )

    assert (
        check_line_item_occurrence(
            invoice, _history("CONSULTING", "CONSULTING", "CONSULTING")
        )
        == []
    )
    assert (
        line_item_key(None, "  On-site   consulting ")
        == "description:on-site consulting"
    )


def test_line_item_occurrence_reports_new_and_rare_items() -> None:
    history = _history(
        "CONSULTING", "CONSULTING", "CONSULTING", "CONSULTING", "SUPPORT"
    )
    invoice = InvoiceExtraction(
        document_type="invoice",
        currency="USD",
        line_items=[
            InvoiceLineItem(product_identifier="SOFTWARE"),
            InvoiceLineItem(product_identifier="SUPPORT"),
        ],
    )

    findings = check_line_item_occurrence(invoice, history)

    assert [finding.finding_type for finding in findings] == [
        "new_line_item",
        "rare_line_item",
    ]
    assert findings[1].details["frequency"] == "0.2"


def test_line_item_occurrence_declares_insufficient_history() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        currency="USD",
        line_items=[InvoiceLineItem(product_identifier="CONSULTING")],
    )

    findings = check_line_item_occurrence(invoice, _history("CONSULTING"))

    assert [finding.finding_type for finding in findings] == ["insufficient_history"]
    assert findings[0].historical_sample_size == 1
