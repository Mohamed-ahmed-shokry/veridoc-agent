"""Repository boundaries for vendor master data and entity resolution."""

from __future__ import annotations

from typing import Protocol

from veridoc.vendors.models import VendorEntity, VendorStatus


class VendorRepository(Protocol):
    """Store and retrieve authoritative vendor master data."""

    def get_vendor_by_id(self, vendor_id: str) -> VendorEntity | None:
        """Return one vendor by its unique vendor identifier, if any."""

    def get_vendor_by_canonical_key(self, canonical_key: str) -> VendorEntity | None:
        """Return one vendor by its canonical slugified key, if any."""

    def find_vendors_by_alias(self, alias_key: str) -> list[VendorEntity]:
        """Return vendors that have an alias matching this canonical key."""

    def find_vendors_by_tax_id(
        self, tax_id: str, tax_type: str | None = None
    ) -> list[VendorEntity]:
        """Return vendors registered with this tax identifier."""

    def find_vendors_by_bank_account(self, account_number: str) -> list[VendorEntity]:
        """Return vendors with this account number or IBAN."""

    def list_vendors(self, *, status: VendorStatus | None = None) -> list[VendorEntity]:
        """Return all registered vendors, optionally filtered by status."""

    def add_vendor(self, vendor: VendorEntity) -> None:
        """Persist one vendor entity and its child records."""
