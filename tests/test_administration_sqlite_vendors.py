"""SQLite integration tests for managed vendor master administration."""

from __future__ import annotations

import pytest

from veridoc.administration.models import (
    ReferenceMetadataInput,
    VendorBankAccountInput,
    VendorInput,
    VendorRecordInput,
    VendorRecordUpdate,
    VendorTaxIdInput,
)
from veridoc.administration.protocol import ReferenceDataConflictError
from veridoc.persistence.sqlite import SQLiteInvoiceRepository


def _repository(tmp_path) -> SQLiteInvoiceRepository:
    repository = SQLiteInvoiceRepository(tmp_path / "reference-data.sqlite")
    repository.initialize()
    return repository


def _record(
    *,
    external_id: str = "vendor-1",
    vendor_id: str = "vnd_001",
    legal_name: str = "Acme Corp",
    canonical_key: str = "acme-corp",
    status: str = "active",
) -> VendorRecordInput:
    return VendorRecordInput(
        metadata=ReferenceMetadataInput(
            source="fixture",
            external_id=external_id,
            retention_until="2027-01-01",
        ),
        vendor=VendorInput(
            vendor_id=vendor_id,
            legal_name=legal_name,
            canonical_key=canonical_key,
            status=status,  # type: ignore[arg-type]
            aliases=["Acme Ltd", "Acme Group"],
            bank_accounts=[
                VendorBankAccountInput(
                    account_number="12345678",
                    iban="GB29NWBK60161331926819",
                    bank_code="NWBK",
                )
            ],
            tax_ids=[
                VendorTaxIdInput(
                    tax_id="GB123456789",
                    tax_type="VAT",
                    country_code="GB",
                )
            ],
        ),
    )


def test_create_vendor_returns_metadata_and_vendor_facts(tmp_path) -> None:
    repository = _repository(tmp_path)

    created = repository.create_vendor(_record())

    assert len(created.metadata.record_id) == 32
    assert created.metadata.source == "fixture"
    assert created.metadata.external_id == "vendor-1"
    assert created.metadata.retention_until is not None
    assert created.vendor.vendor_id == "vnd_001"
    assert created.vendor.legal_name == "Acme Corp"
    assert created.vendor.canonical_key == "acme-corp"
    assert created.vendor.status == "active"
    assert created.vendor.aliases == ["Acme Ltd", "Acme Group"]
    assert len(created.vendor.bank_accounts) == 1
    assert created.vendor.bank_accounts[0].account_number == "12345678"
    assert len(created.vendor.tax_ids) == 1
    assert created.vendor.tax_ids[0].tax_id == "GB123456789"


def test_create_vendor_rejects_duplicate_vendor_id(tmp_path) -> None:
    repository = _repository(tmp_path)
    repository.create_vendor(_record(external_id="vendor-1", vendor_id="vnd_001"))

    with pytest.raises(ReferenceDataConflictError):
        repository.create_vendor(_record(external_id="vendor-2", vendor_id="vnd_001"))


def test_create_vendor_rejects_duplicate_source_external_id(tmp_path) -> None:
    repository = _repository(tmp_path)
    repository.create_vendor(_record(external_id="vendor-1", vendor_id="vnd_001"))

    with pytest.raises(ReferenceDataConflictError):
        repository.create_vendor(_record(external_id="vendor-1", vendor_id="vnd_002"))


def test_get_admin_vendor_finds_by_record_id(tmp_path) -> None:
    repository = _repository(tmp_path)
    created = repository.create_vendor(_record())

    fetched = repository.get_admin_vendor(created.metadata.record_id)
    assert fetched is not None
    assert fetched.metadata.record_id == created.metadata.record_id
    assert fetched.vendor.vendor_id == "vnd_001"

    assert repository.get_admin_vendor("non-existent") is None


def test_list_admin_vendors_supports_pagination_and_status_filter(tmp_path) -> None:
    repository = _repository(tmp_path)
    repository.create_vendor(
        _record(external_id="v-1", vendor_id="vnd_001", status="active")
    )
    repository.create_vendor(
        _record(external_id="v-2", vendor_id="vnd_002", status="suspended")
    )
    repository.create_vendor(
        _record(external_id="v-3", vendor_id="vnd_003", status="active")
    )

    all_page = repository.list_admin_vendors(status=None, offset=0, limit=10)
    assert all_page.total == 3
    assert len(all_page.records) == 3

    paged = repository.list_admin_vendors(status=None, offset=1, limit=1)
    assert paged.total == 3
    assert len(paged.records) == 1
    assert paged.records[0].vendor.vendor_id == "vnd_002"

    active_page = repository.list_admin_vendors(status="active", offset=0, limit=10)
    assert active_page.total == 2
    assert [r.vendor.vendor_id for r in active_page.records] == ["vnd_001", "vnd_003"]


def test_update_admin_vendor_modifies_facts_and_child_records(tmp_path) -> None:
    repository = _repository(tmp_path)
    created = repository.create_vendor(_record())

    updated = repository.update_admin_vendor(
        created.metadata.record_id,
        VendorRecordUpdate(
            vendor=VendorInput(
                vendor_id="vnd_001",
                legal_name="Acme International Ltd",
                canonical_key="acme-international",
                status="suspended",
                aliases=["Acme Int"],
                bank_accounts=[
                    VendorBankAccountInput(
                        account_number="87654321",
                        iban="GB00BARC20000012345678",
                    )
                ],
                tax_ids=[VendorTaxIdInput(tax_id="GB987654321")],
            ),
            retention_until=None,
        ),
    )

    assert updated is not None
    assert updated.metadata.record_id == created.metadata.record_id
    assert updated.vendor.legal_name == "Acme International Ltd"
    assert updated.vendor.canonical_key == "acme-international"
    assert updated.vendor.status == "suspended"
    assert updated.vendor.aliases == ["Acme Int"]
    assert updated.vendor.bank_accounts[0].account_number == "87654321"
    assert updated.vendor.tax_ids[0].tax_id == "GB987654321"

    # Verify query through domain methods
    assert repository.get_vendor_by_canonical_key("acme-international") is not None
    assert len(repository.find_vendors_by_bank_account("87654321")) == 1
    assert len(repository.find_vendors_by_bank_account("12345678")) == 0


def test_update_admin_vendor_returns_none_for_missing_record(tmp_path) -> None:
    repository = _repository(tmp_path)
    result = repository.update_admin_vendor(
        "missing-id",
        VendorRecordUpdate(
            vendor=VendorInput(
                vendor_id="vnd_missing",
                legal_name="Missing",
                canonical_key="missing",
            )
        ),
    )
    assert result is None


def test_delete_admin_vendor_removes_vendor_and_cascades(tmp_path) -> None:
    repository = _repository(tmp_path)
    created = repository.create_vendor(_record())

    deleted = repository.delete_admin_vendor(created.metadata.record_id)
    assert deleted is True

    assert repository.get_admin_vendor(created.metadata.record_id) is None
    assert repository.get_vendor_by_id("vnd_001") is None
    assert repository.find_vendors_by_alias("acme-ltd") == []
    assert repository.find_vendors_by_bank_account("12345678") == []
    assert repository.find_vendors_by_tax_id("GB123456789") == []

    # Second delete returns False
    assert repository.delete_admin_vendor(created.metadata.record_id) is False
