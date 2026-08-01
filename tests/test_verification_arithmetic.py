"""Deterministic invoice arithmetic verification tests."""

from veridoc.extraction.models import InvoiceExtraction, InvoiceLineItem
from veridoc.verification.arithmetic import check_arithmetic


def test_arithmetic_checks_accept_a_consistent_invoice() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        subtotal="200.00",
        tax="40.00",
        discount="10.00",
        total="230.00",
        invoice_date="2026-08-01",
        due_date="2026-08-31",
        line_items=[
            InvoiceLineItem(quantity="2", unit_price="100.00", total_price="200.00")
        ],
    )

    assert check_arithmetic(invoice) == []


def test_arithmetic_checks_report_each_inconsistent_fact() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        subtotal="180.00",
        tax="40.00",
        discount="10.00",
        total="250.00",
        invoice_date="2026-09-01",
        due_date="2026-08-31",
        line_items=[
            InvoiceLineItem(
                product_identifier="CONSULTING",
                quantity="2",
                unit_price="100.00",
                total_price="150.00",
            )
        ],
    )

    findings = check_arithmetic(invoice)

    assert [finding.finding_type for finding in findings] == [
        "invoice_total_mismatch",
        "line_item_amount_mismatch",
        "line_items_subtotal_mismatch",
        "invoice_date_after_due_date",
    ]
    assert findings[1].details["line_item_index"] == 0
    assert findings[2].expected_value == "150.00"
