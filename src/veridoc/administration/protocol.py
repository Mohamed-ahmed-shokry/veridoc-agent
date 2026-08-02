"""Persistence boundary for controlled reference-data administration."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from veridoc.administration.models import (
    ConflictPolicy,
    ImportResult,
    InvoiceRecord,
    InvoiceRecordInput,
    InvoiceRecordPage,
    InvoiceRecordUpdate,
    PurchaseOrderRecord,
    PurchaseOrderRecordInput,
    PurchaseOrderRecordPage,
    PurchaseOrderRecordUpdate,
    ReferenceDataImport,
)


class ReferenceDataConflictError(RuntimeError):
    """Raised when an administrative write conflicts with stored provenance."""

    code = "reference_data_conflict"
    message = "Reference data conflicts with an existing record."

    def __init__(self) -> None:
        super().__init__(self.message)


@runtime_checkable
class ReferenceDataAdminRepository(Protocol):
    """Create, inspect, replace, delete, and import managed reference facts."""

    def create_invoice(self, record: InvoiceRecordInput) -> InvoiceRecord:
        """Create one managed historical invoice."""

    def list_invoices(
        self, *, vendor_key: str | None, offset: int, limit: int
    ) -> InvoiceRecordPage:
        """Return one bounded invoice page."""

    def get_admin_invoice(self, record_id: str) -> InvoiceRecord | None:
        """Return one managed invoice by server identifier."""

    def update_admin_invoice(
        self, record_id: str, update: InvoiceRecordUpdate
    ) -> InvoiceRecord | None:
        """Replace mutable invoice facts while preserving provenance identity."""

    def delete_admin_invoice(self, record_id: str) -> bool:
        """Delete one managed invoice and its line items."""

    def create_purchase_order(
        self, record: PurchaseOrderRecordInput
    ) -> PurchaseOrderRecord:
        """Create one managed purchase order."""

    def list_purchase_orders(
        self, *, vendor_key: str | None, offset: int, limit: int
    ) -> PurchaseOrderRecordPage:
        """Return one bounded purchase-order page."""

    def get_admin_purchase_order(self, record_id: str) -> PurchaseOrderRecord | None:
        """Return one managed purchase order by server identifier."""

    def update_admin_purchase_order(
        self, record_id: str, update: PurchaseOrderRecordUpdate
    ) -> PurchaseOrderRecord | None:
        """Replace mutable purchase-order facts while preserving provenance."""

    def delete_admin_purchase_order(self, record_id: str) -> bool:
        """Delete one managed purchase order and its line items."""

    def import_reference_data(
        self,
        batch: ReferenceDataImport,
        *,
        conflict: ConflictPolicy,
        dry_run: bool,
    ) -> ImportResult:
        """Apply or simulate one validated atomic import."""
