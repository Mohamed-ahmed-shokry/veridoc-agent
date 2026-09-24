"""Persistence boundary for controlled reference-data administration."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from veridoc.administration.models import (
    AdminAuditContext,
    AdminAuditEntry,
    AdminAuditEntryInput,
    AdminAuditPage,
    AuditRecordType,
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
    VendorRecord,
    VendorRecordInput,
    VendorRecordPage,
    VendorRecordUpdate,
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

    def create_invoice(
        self, record: InvoiceRecordInput, *, audit: AdminAuditContext | None = None
    ) -> InvoiceRecord:
        """Create one managed historical invoice."""

    def list_invoices(
        self, *, vendor_key: str | None, offset: int, limit: int
    ) -> InvoiceRecordPage:
        """Return one bounded invoice page."""

    def get_admin_invoice(self, record_id: str) -> InvoiceRecord | None:
        """Return one managed invoice by server identifier."""

    def update_admin_invoice(
        self,
        record_id: str,
        update: InvoiceRecordUpdate,
        *,
        audit: AdminAuditContext | None = None,
    ) -> InvoiceRecord | None:
        """Replace mutable invoice facts while preserving provenance identity."""

    def delete_admin_invoice(
        self, record_id: str, *, audit: AdminAuditContext | None = None
    ) -> bool:
        """Delete one managed invoice and its line items."""

    def create_purchase_order(
        self,
        record: PurchaseOrderRecordInput,
        *,
        audit: AdminAuditContext | None = None,
    ) -> PurchaseOrderRecord:
        """Create one managed purchase order."""

    def list_purchase_orders(
        self, *, vendor_key: str | None, offset: int, limit: int
    ) -> PurchaseOrderRecordPage:
        """Return one bounded purchase-order page."""

    def get_admin_purchase_order(self, record_id: str) -> PurchaseOrderRecord | None:
        """Return one managed purchase order by server identifier."""

    def update_admin_purchase_order(
        self,
        record_id: str,
        update: PurchaseOrderRecordUpdate,
        *,
        audit: AdminAuditContext | None = None,
    ) -> PurchaseOrderRecord | None:
        """Replace mutable purchase-order facts while preserving provenance."""

    def delete_admin_purchase_order(
        self, record_id: str, *, audit: AdminAuditContext | None = None
    ) -> bool:
        """Delete one managed purchase order and its line items."""

    def create_vendor(
        self, record: VendorRecordInput, *, audit: AdminAuditContext | None = None
    ) -> VendorRecord:
        """Create one managed vendor master record."""

    def list_admin_vendors(
        self, *, status: str | None, offset: int, limit: int
    ) -> VendorRecordPage:
        """Return one bounded vendor page."""

    def get_admin_vendor(self, record_id: str) -> VendorRecord | None:
        """Return one managed vendor by server identifier."""

    def update_admin_vendor(
        self,
        record_id: str,
        update: VendorRecordUpdate,
        *,
        audit: AdminAuditContext | None = None,
    ) -> VendorRecord | None:
        """Replace mutable vendor facts while preserving provenance."""

    def delete_admin_vendor(
        self, record_id: str, *, audit: AdminAuditContext | None = None
    ) -> bool:
        """Delete one managed vendor and its aliases, banks, and tax IDs."""

    def import_reference_data(
        self,
        batch: ReferenceDataImport,
        *,
        conflict: ConflictPolicy,
        dry_run: bool,
        audit: AdminAuditContext | None = None,
    ) -> ImportResult:
        """Apply or simulate one validated atomic import."""

    def record_admin_action(self, entry: AdminAuditEntryInput) -> AdminAuditEntry:
        """Append one audit entry for a completed administration mutation."""

    def list_admin_audit_log(
        self,
        *,
        record_type: AuditRecordType | None,
        record_id: str | None,
        offset: int,
        limit: int,
    ) -> AdminAuditPage:
        """Return one bounded audit page ordered by entry sequence."""
