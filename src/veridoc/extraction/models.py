"""Typed invoice extraction values returned by structured extractors."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DocumentType = Literal["invoice", "purchase_order", "unknown"]
EvidenceSource = Literal["ocr_text", "page_image"]


class EvidenceReference(BaseModel):
    """A page-level source supporting one extracted field."""

    model_config = ConfigDict(extra="forbid")

    page_number: int = Field(ge=1)
    source: EvidenceSource
    text_span: str | None = None


class ExtractionUncertainty(BaseModel):
    """A declared limitation or ambiguity in the extraction result."""

    model_config = ConfigDict(extra="forbid")

    field: str | None = None
    reason: str = Field(min_length=1)


class InvoiceLineItem(BaseModel):
    """One optional invoice line item without inferred values."""

    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    product_identifier: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    total_price: Decimal | None = None
    evidence: list[EvidenceReference] = Field(default_factory=list)


class InvoiceExtraction(BaseModel):
    """Structured invoice data and evidence produced by Phase 2 extraction."""

    model_config = ConfigDict(extra="forbid")

    document_type: DocumentType
    vendor_name: str | None = None
    vendor_identifier: str | None = None
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
    line_items: list[InvoiceLineItem] = Field(default_factory=list)
    ocr_confidence: float | None = Field(default=None, ge=0, le=100)
    extraction_confidence: float | None = Field(default=None, ge=0, le=100)
    evidence: dict[str, list[EvidenceReference]] = Field(default_factory=dict)
    uncertainties: list[ExtractionUncertainty] = Field(default_factory=list)
