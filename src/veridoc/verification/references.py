"""Reference facts used by deterministic invoice verification."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ReferenceLineItem(BaseModel):
    """One historical or purchase-order line item."""

    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    product_identifier: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    total_price: Decimal | None = None


class HistoricalInvoice(BaseModel):
    """Persisted vendor invoice facts available for comparison."""

    model_config = ConfigDict(extra="forbid")

    vendor_key: str = Field(min_length=1)
    invoice_number: str | None = None
    purchase_order_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    discount: Decimal | None = None
    total: Decimal | None = None
    payment_terms: str | None = None
    line_items: list[ReferenceLineItem] = Field(default_factory=list)


class PurchaseOrder(BaseModel):
    """Persisted purchase-order facts available for reconciliation."""

    model_config = ConfigDict(extra="forbid")

    vendor_key: str = Field(min_length=1)
    purchase_order_number: str = Field(min_length=1)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    total: Decimal | None = None
    line_items: list[ReferenceLineItem] = Field(default_factory=list)
