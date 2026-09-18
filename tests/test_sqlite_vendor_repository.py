"""Tests for SQLite vendor repository persistence and lookups."""

import sqlite3
from pathlib import Path

import pytest

from veridoc.persistence.protocol import ReferenceDataUnavailableError
from veridoc.persistence.sqlite import (
    InvalidPersistedReferenceDataError,
    SQLiteInvoiceRepository,
    SQLiteVendorRepository,
    validate_persisted_reference_data,
)
from veridoc.vendors.models import (
    VendorBankAccount,
    VendorEntity,
    VendorTaxId,
    derive_canonical_vendor_key,
)


def _make_vendor(
    vendor_id: str = "vnd_001",
    name: str = "Acme Supplies Ltd",
    status: str = "active",
    aliases: list[str] | None = None,
    bank_accounts: list[VendorBankAccount] | None = None,
    tax_ids: list[VendorTaxId] | None = None,
) -> VendorEntity:
    suffix = "".join(c for c in vendor_id if c.isdigit()) or "001"
    default_banks = [
        VendorBankAccount(
            account_number=f"12345{suffix}",
            bank_code="BARC",
            iban=f"GB82BARC20000012345{suffix}",
            routing_number="20-00-00",
        ),
        VendorBankAccount(
            account_number=f"87654{suffix}",
            bank_code="HSBC",
            iban=None,
            routing_number=None,
        ),
    ]
    default_taxes = [
        VendorTaxId(tax_id=f"GB {suffix} 4567 89", tax_type="VAT", country_code="GB"),
        VendorTaxId(tax_id=f"{suffix}-3456789", tax_type="EIN", country_code="US"),
    ]
    return VendorEntity(
        vendor_id=vendor_id,
        legal_name=name,
        canonical_key=derive_canonical_vendor_key(name),
        status=status,  # type: ignore[arg-type]
        aliases=aliases if aliases is not None else ["Acme Supplies", "Acme Corp"],
        bank_accounts=bank_accounts if bank_accounts is not None else default_banks,
        tax_ids=tax_ids if tax_ids is not None else default_taxes,
        record_id=f"rec_{vendor_id}",
        source="test",
        external_id=f"ext_{vendor_id}",
        created_at="2026-09-18T00:00:00Z",
        updated_at="2026-09-18T00:00:00Z",
        retention_until=None,
    )


def test_sqlite_vendor_repository_round_trips_vendor_entity(tmp_path: Path) -> None:
    repo = SQLiteVendorRepository(tmp_path / "reference.sqlite")
    repo.initialize()

    vendor = _make_vendor()
    repo.add_vendor(vendor)

    retrieved = repo.get_vendor_by_id("vnd_001")
    assert retrieved is not None
    assert retrieved.vendor_id == "vnd_001"
    assert retrieved.legal_name == "Acme Supplies Ltd"
    assert retrieved.canonical_key == "acme-supplies-ltd"
    assert retrieved.status == "active"
    assert retrieved.aliases == ["Acme Supplies", "Acme Corp"]
    assert len(retrieved.bank_accounts) == 2
    assert retrieved.bank_accounts[0].account_number == "12345001"
    assert retrieved.bank_accounts[0].iban == "GB82BARC20000012345001"
    assert retrieved.bank_accounts[1].account_number == "87654001"
    assert len(retrieved.tax_ids) == 2
    assert retrieved.tax_ids[0].tax_id == "GB 001 4567 89"
    assert retrieved.tax_ids[0].tax_type == "VAT"
    assert retrieved.tax_ids[0].country_code == "GB"


def test_sqlite_vendor_repository_lookups(tmp_path: Path) -> None:
    repo = SQLiteInvoiceRepository(tmp_path / "reference.sqlite")
    repo.initialize()

    vendor1 = _make_vendor(
        "vnd_001",
        "Acme Supplies Ltd",
        "active",
        aliases=["Acme Supplies", "Acme Corp"],
    )
    vendor2 = _make_vendor(
        "vnd_002",
        "Beta Logistics Inc",
        "suspended",
        aliases=["Beta Logistics"],
    )
    repo.add_vendor(vendor1)
    repo.add_vendor(vendor2)

    # get_vendor_by_canonical_key
    assert repo.get_vendor_by_canonical_key("acme-supplies-ltd") is not None
    assert repo.get_vendor_by_canonical_key("nonexistent") is None

    # find_vendors_by_alias
    acme_alias_matches = repo.find_vendors_by_alias("acme-supplies")
    assert len(acme_alias_matches) == 1
    assert acme_alias_matches[0].vendor_id == "vnd_001"
    assert repo.find_vendors_by_alias("nonexistent-alias") == []

    # find_vendors_by_tax_id (exact and stripped punctuation)
    tax_matches = repo.find_vendors_by_tax_id("GB001456789")
    assert len(tax_matches) == 1
    assert tax_matches[0].vendor_id == "vnd_001"

    ein_matches = repo.find_vendors_by_tax_id("0013456789", tax_type="EIN")
    assert len(ein_matches) == 1
    assert ein_matches[0].vendor_id == "vnd_001"

    wrong_type = repo.find_vendors_by_tax_id("0013456789", tax_type="WRONG")
    assert wrong_type == []

    # find_vendors_by_bank_account (by account number and by IBAN)
    bank_matches = repo.find_vendors_by_bank_account("12345001")
    assert len(bank_matches) == 1
    assert bank_matches[0].vendor_id == "vnd_001"

    iban_matches = repo.find_vendors_by_bank_account("GB82 BARC 2000 0012 3450 01")
    assert len(iban_matches) == 1
    assert iban_matches[0].vendor_id == "vnd_001"

    # list_vendors
    all_vendors = repo.list_vendors()
    assert len(all_vendors) == 2
    active_vendors = repo.list_vendors(status="active")
    assert len(active_vendors) == 1
    assert active_vendors[0].vendor_id == "vnd_001"
    suspended_vendors = repo.list_vendors(status="suspended")
    assert len(suspended_vendors) == 1
    assert suspended_vendors[0].vendor_id == "vnd_002"
    inactive_vendors = repo.list_vendors(status="inactive")
    assert len(inactive_vendors) == 0


def test_sqlite_vendor_repository_rejects_duplicate_vendor_id(
    tmp_path: Path,
) -> None:
    repo = SQLiteVendorRepository(tmp_path / "reference.sqlite")
    repo.initialize()

    vendor = _make_vendor("vnd_001", "Acme Supplies Ltd")
    repo.add_vendor(vendor)

    duplicate = _make_vendor("vnd_001", "Different Name")
    with pytest.raises(ReferenceDataUnavailableError):
        repo.add_vendor(duplicate)


def test_validate_persisted_reference_data_with_vendors(tmp_path: Path) -> None:
    database_path = tmp_path / "reference.sqlite"
    repo = SQLiteVendorRepository(database_path)
    repo.initialize()
    repo.add_vendor(_make_vendor())

    with sqlite3.connect(database_path) as connection:
        # Valid database succeeds
        validate_persisted_reference_data(connection)

        # Corrupt a status column
        connection.execute("UPDATE vendors SET status = 'invalid_status'")
        connection.commit()

        with pytest.raises(InvalidPersistedReferenceDataError):
            validate_persisted_reference_data(connection)
