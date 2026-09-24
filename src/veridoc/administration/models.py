"""Bounded schemas for reference-data administration."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from veridoc.vendors.models import (
    VendorBankAccount,
    VendorEntity,
    VendorStatus,
    VendorTaxId,
)
from veridoc.verification.references import (
    HistoricalInvoice,
    PurchaseOrder,
)
from veridoc.verification.vendors import normalize_vendor_key

MAX_ADMIN_IMPORT_BYTES = 1024 * 1024
MAX_IMPORT_RECORDS = 500
MAX_REFERENCE_LINE_ITEMS = 200

BoundedAmount = Annotated[Decimal, Field(max_digits=24, decimal_places=6)]
ConflictPolicy = Literal["reject", "skip", "replace"]


def _canonical_vendor_key(value: str) -> str:
    normalized = normalize_vendor_key(value)
    if normalized is None or len(normalized) > 128:
        raise ValueError("vendor_key must produce a canonical key of 1-128 characters")
    return normalized


VendorKey = Annotated[
    str,
    Field(min_length=1, max_length=128),
    AfterValidator(_canonical_vendor_key),
]


class AdministrationModel(BaseModel):
    """Strict base model for untrusted administrative data."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class ReferenceLineItemInput(AdministrationModel):
    """One bounded line item supplied by an administrator."""

    description: str | None = Field(default=None, max_length=500)
    product_identifier: str | None = Field(default=None, max_length=128)
    quantity: BoundedAmount | None = None
    unit_price: BoundedAmount | None = None
    total_price: BoundedAmount | None = None


class InvoiceReferenceInput(AdministrationModel):
    """Validated invoice facts that may enter reference history."""

    vendor_key: VendorKey
    invoice_number: str | None = Field(default=None, max_length=128)
    purchase_order_number: str | None = Field(default=None, max_length=128)
    invoice_date: date | None = None
    due_date: date | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    subtotal: BoundedAmount | None = None
    tax: BoundedAmount | None = None
    discount: BoundedAmount | None = None
    total: BoundedAmount | None = None
    payment_terms: str | None = Field(default=None, max_length=200)
    line_items: list[ReferenceLineItemInput] = Field(
        default_factory=list,
        max_length=MAX_REFERENCE_LINE_ITEMS,
    )

    def to_domain(self) -> HistoricalInvoice:
        """Convert validated administrative input to verification facts."""
        return HistoricalInvoice.model_validate(self.model_dump())


class PurchaseOrderReferenceInput(AdministrationModel):
    """Validated purchase-order facts available for reconciliation."""

    vendor_key: VendorKey
    purchase_order_number: str = Field(min_length=1, max_length=128)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    total: BoundedAmount | None = None
    line_items: list[ReferenceLineItemInput] = Field(
        default_factory=list,
        max_length=MAX_REFERENCE_LINE_ITEMS,
    )

    def to_domain(self) -> PurchaseOrder:
        """Convert validated administrative input to verification facts."""
        return PurchaseOrder.model_validate(self.model_dump())


class VendorBankAccountInput(AdministrationModel):
    """One verified bank account or remittance coordinates."""

    account_number: str = Field(min_length=1, max_length=64)
    bank_code: str | None = Field(default=None, max_length=32)
    iban: str | None = Field(default=None, max_length=64)
    routing_number: str | None = Field(default=None, max_length=32)


class VendorTaxIdInput(AdministrationModel):
    """One official tax or registration identifier."""

    tax_id: str = Field(min_length=1, max_length=64)
    tax_type: str = Field(default="VAT", min_length=1, max_length=32)
    country_code: str | None = Field(default=None, min_length=2, max_length=3)


class VendorInput(AdministrationModel):
    """Validated vendor master facts managed in the vendor registry."""

    vendor_id: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
    )
    legal_name: str = Field(min_length=1, max_length=256)
    canonical_key: VendorKey
    status: VendorStatus = "active"
    aliases: list[str] = Field(default_factory=list, max_length=50)
    bank_accounts: list[VendorBankAccountInput] = Field(
        default_factory=list,
        max_length=50,
    )
    tax_ids: list[VendorTaxIdInput] = Field(
        default_factory=list,
        max_length=50,
    )

    def to_domain(self) -> VendorEntity:
        """Convert validated administrative input to vendor master entity."""
        return VendorEntity(
            vendor_id=self.vendor_id,
            legal_name=self.legal_name,
            canonical_key=self.canonical_key,
            status=self.status,
            aliases=list(self.aliases),
            bank_accounts=[
                VendorBankAccount(
                    account_number=b.account_number,
                    bank_code=b.bank_code,
                    iban=b.iban,
                    routing_number=b.routing_number,
                )
                for b in self.bank_accounts
            ],
            tax_ids=[
                VendorTaxId(
                    tax_id=t.tax_id,
                    tax_type=t.tax_type,
                    country_code=t.country_code,
                )
                for t in self.tax_ids
            ],
        )


class ReferenceMetadataInput(AdministrationModel):
    """Client-supplied provenance and retention metadata."""

    source: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    external_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$",
    )
    retention_until: date | None = None


class ReferenceRecordMetadata(ReferenceMetadataInput):
    """Server-managed identity and timestamps for one reference record."""

    record_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
    )
    created_at: AwareDatetime
    updated_at: AwareDatetime


class InvoiceRecordInput(AdministrationModel):
    """One invoice record accepted for create or import."""

    metadata: ReferenceMetadataInput
    invoice: InvoiceReferenceInput


class PurchaseOrderRecordInput(AdministrationModel):
    """One purchase-order record accepted for create or import."""

    metadata: ReferenceMetadataInput
    purchase_order: PurchaseOrderReferenceInput


class VendorRecordInput(AdministrationModel):
    """One vendor master record accepted for create or import."""

    metadata: ReferenceMetadataInput
    vendor: VendorInput


class InvoiceRecordUpdate(AdministrationModel):
    """Mutable invoice facts and retention metadata."""

    invoice: InvoiceReferenceInput
    retention_until: date | None = None


class PurchaseOrderRecordUpdate(AdministrationModel):
    """Mutable purchase-order facts and retention metadata."""

    purchase_order: PurchaseOrderReferenceInput
    retention_until: date | None = None


class VendorRecordUpdate(AdministrationModel):
    """Mutable vendor master facts and retention metadata."""

    vendor: VendorInput
    retention_until: date | None = None


class InvoiceRecord(AdministrationModel):
    """One stored invoice with safe administrative metadata."""

    metadata: ReferenceRecordMetadata
    invoice: InvoiceReferenceInput


class PurchaseOrderRecord(AdministrationModel):
    """One stored purchase order with safe administrative metadata."""

    metadata: ReferenceRecordMetadata
    purchase_order: PurchaseOrderReferenceInput


class VendorRecord(AdministrationModel):
    """One stored vendor with safe administrative metadata."""

    metadata: ReferenceRecordMetadata
    vendor: VendorInput


class ReferenceDataImport(AdministrationModel):
    """One bounded invoice, purchase-order, and vendor import batch."""

    invoices: list[InvoiceRecordInput] = Field(
        default_factory=list,
        max_length=MAX_IMPORT_RECORDS,
    )
    purchase_orders: list[PurchaseOrderRecordInput] = Field(
        default_factory=list,
        max_length=MAX_IMPORT_RECORDS,
    )
    vendors: list[VendorRecordInput] = Field(
        default_factory=list,
        max_length=MAX_IMPORT_RECORDS,
    )

    @model_validator(mode="after")
    def validate_record_count(self) -> Self:
        count = len(self.invoices) + len(self.purchase_orders) + len(self.vendors)
        if count == 0:
            raise ValueError("Import must contain at least one reference record.")
        if count > MAX_IMPORT_RECORDS:
            raise ValueError(
                f"Import cannot contain more than {MAX_IMPORT_RECORDS} records."
            )
        return self


class ImportResult(AdministrationModel):
    """Counts produced by one import transaction or dry run."""

    dry_run: bool
    created: int = Field(ge=0)
    replaced: int = Field(ge=0)
    skipped: int = Field(ge=0)


class InvoiceRecordPage(AdministrationModel):
    """One bounded page of managed invoices."""

    records: list[InvoiceRecord]
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)
    total: int = Field(ge=0)


class PurchaseOrderRecordPage(AdministrationModel):
    """One bounded page of managed purchase orders."""

    records: list[PurchaseOrderRecord]
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)
    total: int = Field(ge=0)


class VendorRecordPage(AdministrationModel):
    """One bounded page of managed vendors."""

    records: list[VendorRecord]
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)
    total: int = Field(ge=0)


AuditOperation = Literal["create", "update", "delete", "import"]
AuditRecordType = Literal["invoice", "purchase_order", "vendor"]
AuditActor = Literal["admin"]

_REQUEST_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
_RECORD_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]*$"


class AdminAuditEntryInput(AdministrationModel):
    """One bounded administration mutation record for the audit log."""

    occurred_at: AwareDatetime
    request_id: str = Field(min_length=1, max_length=128, pattern=_REQUEST_ID_PATTERN)
    actor: AuditActor
    operation: AuditOperation
    record_type: AuditRecordType
    record_id: str = Field(min_length=1, max_length=128, pattern=_RECORD_ID_PATTERN)
    before_json: str | None = Field(default=None, max_length=MAX_ADMIN_IMPORT_BYTES)
    after_json: str | None = Field(default=None, max_length=MAX_ADMIN_IMPORT_BYTES)


class AdminAuditEntry(AdminAuditEntryInput):
    """One persisted audit entry with its server sequence identifier."""

    entry_id: int = Field(ge=1)


class AdminAuditPage(AdministrationModel):
    """One bounded page of audit entries, newest last."""

    records: list[AdminAuditEntry]
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)
    total: int = Field(ge=0)


class AdminAuditContext(AdministrationModel):
    """Request-scoped identity stamped on audit entries for one mutation call."""

    request_id: str = Field(min_length=1, max_length=128, pattern=_REQUEST_ID_PATTERN)
    actor: AuditActor
    occurred_at: AwareDatetime
