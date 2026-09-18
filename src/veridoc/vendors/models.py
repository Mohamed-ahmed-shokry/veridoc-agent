"""Typed domain models for vendor master data and entity resolution."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VendorStatus = Literal["active", "suspended", "inactive"]
VendorMatchConfidence = Literal[
    "exact_tax",
    "exact_bank",
    "exact_alias",
    "fuzzy_name",
    "unresolved",
]


class VendorBankAccount(BaseModel):
    """A verified bank account or remittance coordinates for one vendor."""

    model_config = ConfigDict(extra="forbid")

    account_number: str = Field(min_length=1, max_length=64)
    bank_code: str | None = Field(default=None, max_length=32)
    iban: str | None = Field(default=None, max_length=64)
    routing_number: str | None = Field(default=None, max_length=32)


class VendorTaxId(BaseModel):
    """An official tax or corporate registration identifier for one vendor."""

    model_config = ConfigDict(extra="forbid")

    tax_id: str = Field(min_length=1, max_length=64)
    tax_type: str = Field(default="VAT", min_length=1, max_length=32)
    country_code: str | None = Field(default=None, min_length=2, max_length=3)


class VendorEntity(BaseModel):
    """An authoritative vendor master entity with aliases and financial details."""

    model_config = ConfigDict(extra="forbid")

    vendor_id: str = Field(min_length=1, max_length=64)
    legal_name: str = Field(min_length=1, max_length=256)
    canonical_key: str = Field(min_length=1, max_length=128)
    status: VendorStatus = "active"
    aliases: list[str] = Field(default_factory=list)
    bank_accounts: list[VendorBankAccount] = Field(default_factory=list)
    tax_ids: list[VendorTaxId] = Field(default_factory=list)
    record_id: str | None = None
    source: str | None = None
    external_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    retention_until: str | None = None


class VendorResolutionResult(BaseModel):
    """The outcome of matching an extracted invoice against vendor master data."""

    model_config = ConfigDict(extra="forbid")

    resolved_vendor_id: str | None = None
    canonical_key: str | None = None
    legal_name: str | None = None
    confidence: VendorMatchConfidence
    score: float = Field(ge=0.0, le=1.0)
    matched_attribute: str | None = None
    status: VendorStatus | None = None
