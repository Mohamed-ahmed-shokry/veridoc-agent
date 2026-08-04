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


class InvoiceRecordUpdate(AdministrationModel):
    """Mutable invoice facts and retention metadata."""

    invoice: InvoiceReferenceInput
    retention_until: date | None = None


class PurchaseOrderRecordUpdate(AdministrationModel):
    """Mutable purchase-order facts and retention metadata."""

    purchase_order: PurchaseOrderReferenceInput
    retention_until: date | None = None


class InvoiceRecord(AdministrationModel):
    """One stored invoice with safe administrative metadata."""

    metadata: ReferenceRecordMetadata
    invoice: InvoiceReferenceInput


class PurchaseOrderRecord(AdministrationModel):
    """One stored purchase order with safe administrative metadata."""

    metadata: ReferenceRecordMetadata
    purchase_order: PurchaseOrderReferenceInput


class ReferenceDataImport(AdministrationModel):
    """One bounded invoice and purchase-order import batch."""

    invoices: list[InvoiceRecordInput] = Field(
        default_factory=list,
        max_length=MAX_IMPORT_RECORDS,
    )
    purchase_orders: list[PurchaseOrderRecordInput] = Field(
        default_factory=list,
        max_length=MAX_IMPORT_RECORDS,
    )

    @model_validator(mode="after")
    def validate_record_count(self) -> Self:
        count = len(self.invoices) + len(self.purchase_orders)
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
