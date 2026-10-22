"""Line item completeness verification tests."""

from decimal import Decimal

from veridoc.extraction.models import InvoiceExtraction, InvoiceLineItem
from veridoc.verification.line_item_completeness import check_line_item_completeness


def _invoice(*line_items: InvoiceLineItem) -> InvoiceExtraction:
    return InvoiceExtraction(document_type="invoice", line_items=list(line_items))


def test_completeness_accepts_invoices_without_line_items() -> None:
    assert check_line_item_completeness(_invoice()) == []


def test_completeness_accepts_lines_with_total_price() -> None:
    invoice = _invoice(
        InvoiceLineItem(description="Consulting", total_price=Decimal("100.00"))
    )

    assert check_line_item_completeness(invoice) == []


def test_completeness_accepts_lines_with_derivable_amounts() -> None:
    invoice = _invoice(
        InvoiceLineItem(
            product_identifier="SKU-1",
            quantity=Decimal(2),
            unit_price=Decimal("50.00"),
        )
    )

    assert check_line_item_completeness(invoice) == []


def test_completeness_reports_missing_identity() -> None:
    invoice = _invoice(InvoiceLineItem(total_price=Decimal("100.00")))

    findings = check_line_item_completeness(invoice)

    assert [finding.finding_type for finding in findings] == ["incomplete_line_item"]
    assert findings[0].severity == "medium"
    assert findings[0].comparison_source == "invoice_line_items"
    assert findings[0].details == {"line_item_index": 0, "field": "identity"}
    assert findings[0].expected_value == "identity"


def test_completeness_treats_blank_identity_as_missing() -> None:
    invoice = _invoice(
        InvoiceLineItem(
            description="   ",
            product_identifier="",
            total_price=Decimal("100.00"),
        )
    )

    findings = check_line_item_completeness(invoice)

    assert [finding.details["field"] for finding in findings] == ["identity"]


def test_completeness_reports_missing_amount() -> None:
    invoice = _invoice(InvoiceLineItem(description="Consulting"))

    findings = check_line_item_completeness(invoice)

    assert [finding.finding_type for finding in findings] == ["incomplete_line_item"]
    assert findings[0].severity == "medium"
    assert findings[0].details == {"line_item_index": 0, "field": "amount"}
    assert findings[0].expected_value == "amount"


def test_completeness_reports_partial_price_inputs() -> None:
    invoice = _invoice(
        InvoiceLineItem(description="Consulting", quantity=Decimal(2)),
        InvoiceLineItem(description="Support", unit_price=Decimal("10.00")),
    )

    findings = check_line_item_completeness(invoice)

    assert [finding.details["line_item_index"] for finding in findings] == [0, 1]
    assert [finding.details["field"] for finding in findings] == ["amount", "amount"]


def test_completeness_reports_both_gaps_identity_before_amount() -> None:
    invoice = _invoice(InvoiceLineItem())

    findings = check_line_item_completeness(invoice)

    assert [finding.details["field"] for finding in findings] == [
        "identity",
        "amount",
    ]
    assert [finding.details["line_item_index"] for finding in findings] == [0, 0]


def test_completeness_orders_findings_by_line_item() -> None:
    invoice = _invoice(
        InvoiceLineItem(description="Complete", total_price=Decimal("1.00")),
        InvoiceLineItem(total_price=Decimal("2.00")),
        InvoiceLineItem(description="No amount"),
    )

    findings = check_line_item_completeness(invoice)

    assert [finding.details for finding in findings] == [
        {"line_item_index": 1, "field": "identity"},
        {"line_item_index": 2, "field": "amount"},
    ]


def test_completeness_accepts_zero_total_price() -> None:
    invoice = _invoice(
        InvoiceLineItem(description="Zero-rated", total_price=Decimal(0))
    )

    assert check_line_item_completeness(invoice) == []


def test_completeness_does_not_mutate_the_invoice() -> None:
    invoice = _invoice(
        InvoiceLineItem(
            product_identifier="SKU-1",
            quantity=Decimal(2),
            unit_price=Decimal("50.00"),
        )
    )
    original = invoice.model_copy(deep=True)

    check_line_item_completeness(invoice)

    assert invoice == original
