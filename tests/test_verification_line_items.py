"""Vendor-history line-item occurrence tests with synthetic data."""

from veridoc.extraction.models import InvoiceExtraction, InvoiceLineItem
from veridoc.verification.line_items import (
    check_line_item_occurrence,
    check_line_item_statistics,
    line_item_key,
)
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


def test_line_item_statistics_accepts_established_price_and_quantity() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        currency="USD",
        line_items=[
            InvoiceLineItem(
                product_identifier="CONSULTING", quantity="2", unit_price="3000.00"
            )
        ],
    )
    history = [
        HistoricalInvoice(
            vendor_key="fictional-supplies",
            invoice_number=f"INV-{index}",
            currency="USD",
            line_items=[
                ReferenceLineItem(
                    product_identifier="CONSULTING",
                    quantity=quantity,
                    unit_price=price,
                )
            ],
        )
        for index, (quantity, price) in enumerate(
            [("1", "2900.00"), ("2", "3000.00"), ("3", "3100.00")], start=1
        )
    ]

    assert check_line_item_statistics(invoice, history) == []


def test_line_item_statistics_reports_price_and_quantity_outliers() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        currency="USD",
        line_items=[
            InvoiceLineItem(
                product_identifier="CONSULTING", quantity="10", unit_price="9200.00"
            )
        ],
    )
    history = [
        HistoricalInvoice(
            vendor_key="fictional-supplies",
            invoice_number=f"INV-{index}",
            currency="USD",
            line_items=[
                ReferenceLineItem(
                    product_identifier="CONSULTING",
                    quantity=quantity,
                    unit_price=price,
                )
            ],
        )
        for index, (quantity, price) in enumerate(
            [("1", "2900.00"), ("2", "3000.00"), ("3", "3100.00")], start=1
        )
    ]

    findings = check_line_item_statistics(invoice, history)

    assert [finding.finding_type for finding in findings] == [
        "historical_line_item_price_outlier",
        "historical_line_item_quantity_outlier",
    ]
    assert all(
        finding.z_score is not None and finding.z_score > 3 for finding in findings
    )
