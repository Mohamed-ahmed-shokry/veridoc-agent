"""Purchase-order reconciliation tests using synthetic reference data."""

from veridoc.extraction.models import InvoiceExtraction, InvoiceLineItem
from veridoc.verification.purchase_orders import check_purchase_order
from veridoc.verification.references import PurchaseOrder, ReferenceLineItem


class PurchaseOrderRepository:
    """Minimal synthetic purchase-order lookup for reconciliation tests."""

    def get_purchase_order(
        self, vendor_key: str, purchase_order_number: str
    ) -> PurchaseOrder | None:
        if (vendor_key, purchase_order_number) == ("fictional-supplies", "PO-001"):
            return PurchaseOrder(
                vendor_key=vendor_key,
                purchase_order_number=purchase_order_number,
                currency="USD",
                total="7200.00",
            )
        if (vendor_key, purchase_order_number) == ("fictional-supplies", "PO-002"):
            return PurchaseOrder(
                vendor_key=vendor_key,
                purchase_order_number=purchase_order_number,
                line_items=[
                    ReferenceLineItem(
                        product_identifier="CONSULTING",
                        quantity="2",
                        unit_price="3000.00",
                        total_price="6000.00",
                    )
                ],
            )
        if (vendor_key, purchase_order_number) == ("fictional-supplies", "PO-003"):
            return PurchaseOrder(
                vendor_key=vendor_key,
                purchase_order_number=purchase_order_number,
                line_items=[
                    ReferenceLineItem(
                        product_identifier="CONSULTING",
                        quantity="2",
                        unit_price="3000.00",
                        total_price="6000.00",
                    ),
                    ReferenceLineItem(
                        product_identifier="CONSULTING",
                        quantity="1",
                        unit_price="1000.00",
                        total_price="1000.00",
                    ),
                ],
            )
        return None


def test_purchase_order_check_accepts_matching_invoice_facts() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies",
        purchase_order_number="PO-001",
        currency="USD",
        total="7200.00",
    )

    assert check_purchase_order(invoice, PurchaseOrderRepository()) == []


def test_purchase_order_check_reports_missing_and_mismatched_references() -> None:
    repository = PurchaseOrderRepository()
    unknown_purchase_order = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies",
        purchase_order_number="PO-404",
    )
    mismatched_invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies",
        purchase_order_number="PO-001",
        currency="EUR",
        total="8200.00",
    )

    missing_findings = check_purchase_order(unknown_purchase_order, repository)
    mismatch_findings = check_purchase_order(mismatched_invoice, repository)

    assert missing_findings[0].finding_type == "purchase_order_mismatch"
    assert [finding.details["field"] for finding in mismatch_findings] == [
        "currency",
        "total",
    ]


def test_purchase_order_check_reports_line_item_mismatches() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies",
        purchase_order_number="PO-002",
        line_items=[
            InvoiceLineItem(
                product_identifier="CONSULTING",
                quantity="3",
                unit_price="3100.00",
                total_price="9300.00",
            ),
            InvoiceLineItem(product_identifier="SOFTWARE"),
        ],
    )

    findings = check_purchase_order(invoice, PurchaseOrderRepository())

    assert [finding.details["field"] for finding in findings] == [
        "line_item_quantity",
        "line_item_unit_price",
        "line_item_total_price",
        "line_item",
    ]


def test_purchase_order_check_matches_duplicate_line_items_once() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies",
        purchase_order_number="PO-003",
        line_items=[
            InvoiceLineItem(
                product_identifier="CONSULTING",
                quantity="2",
                unit_price="3000.00",
                total_price="6000.00",
            ),
            InvoiceLineItem(
                product_identifier="CONSULTING",
                quantity="1",
                unit_price="1000.00",
                total_price="1000.00",
            ),
        ],
    )

    assert check_purchase_order(invoice, PurchaseOrderRepository()) == []
