"""Repository boundary used by deterministic verification."""

from __future__ import annotations

from typing import Protocol

from veridoc.verification.references import HistoricalInvoice, PurchaseOrder


class ReferenceDataUnavailableError(RuntimeError):
    """Raised when reference data cannot be read or written safely."""

    code = "reference_data_unavailable"
    message = "Reference data is not available on this server."

    def __init__(self) -> None:
        super().__init__(self.message)


class InvoiceRepository(Protocol):
    """Store and retrieve vendor invoices and purchase orders."""

    def add_invoice(self, invoice: HistoricalInvoice) -> None:
        """Persist one historical vendor invoice."""

    def add_purchase_order(self, purchase_order: PurchaseOrder) -> None:
        """Persist one vendor purchase order."""

    def list_vendor_invoices(self, vendor_key: str) -> list[HistoricalInvoice]:
        """Return all persisted invoices for one vendor."""

    def find_invoice(
        self, vendor_key: str, invoice_number: str
    ) -> HistoricalInvoice | None:
        """Return an invoice with this vendor-local invoice number, if any."""

    def get_purchase_order(
        self, vendor_key: str, purchase_order_number: str
    ) -> PurchaseOrder | None:
        """Return a vendor purchase order by its number, if any."""
