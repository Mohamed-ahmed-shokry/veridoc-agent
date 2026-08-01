"""SQLite repository integration tests using synthetic reference facts."""

from decimal import Decimal

from veridoc.persistence.sqlite import SQLiteInvoiceRepository
from veridoc.verification.references import (
    HistoricalInvoice,
    PurchaseOrder,
    ReferenceLineItem,
)


def test_sqlite_repository_round_trips_vendor_invoice_history(tmp_path) -> None:
    repository = SQLiteInvoiceRepository(tmp_path / "reference-data.sqlite")
    repository.initialize()
    invoice = HistoricalInvoice(
        vendor_key="fictional-supplies",
        invoice_number="INV-001",
        purchase_order_number="PO-001",
        invoice_date="2026-07-01",
        due_date="2026-07-31",
        currency="USD",
        subtotal="6000.00",
        tax="1200.00",
        total="7200.00",
        payment_terms="Net 30",
        line_items=[
            ReferenceLineItem(
                product_identifier="CONSULTING",
                quantity="2",
                unit_price="3000.00",
                total_price="6000.00",
            )
        ],
    )

    repository.add_invoice(invoice)

    assert repository.list_vendor_invoices("fictional-supplies") == [invoice]
    assert repository.list_vendor_invoices("other-vendor") == []


def test_sqlite_repository_finds_duplicate_invoice_and_purchase_order(tmp_path) -> None:
    repository = SQLiteInvoiceRepository(tmp_path / "reference-data.sqlite")
    repository.initialize()
    invoice = HistoricalInvoice(
        vendor_key="fictional-supplies", invoice_number="INV-001"
    )
    purchase_order = PurchaseOrder(
        vendor_key="fictional-supplies",
        purchase_order_number="PO-001",
        currency="USD",
        total=Decimal("7200.00"),
    )
    repository.add_invoice(invoice)
    repository.add_purchase_order(purchase_order)

    assert repository.find_invoice("fictional-supplies", "INV-001") == invoice
    assert repository.find_invoice("fictional-supplies", "INV-404") is None
    assert (
        repository.get_purchase_order("fictional-supplies", "PO-001") == purchase_order
    )
    assert repository.get_purchase_order("fictional-supplies", "PO-404") is None
