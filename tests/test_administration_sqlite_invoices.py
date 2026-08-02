"""SQLite integration tests for managed invoice administration."""

import sqlite3

import pytest

from veridoc.administration.models import (
    InvoiceRecordInput,
    InvoiceRecordUpdate,
    InvoiceReferenceInput,
    ReferenceLineItemInput,
    ReferenceMetadataInput,
)
from veridoc.administration.protocol import ReferenceDataConflictError
from veridoc.persistence.sqlite import SQLiteInvoiceRepository
from veridoc.verification.references import HistoricalInvoice


def _repository(tmp_path) -> SQLiteInvoiceRepository:
    repository = SQLiteInvoiceRepository(tmp_path / "reference-data.sqlite")
    repository.initialize()
    return repository


def _record(
    *,
    external_id: str = "invoice-1",
    vendor_key: str = "fictional-supplies",
    invoice_number: str = "INV-001",
) -> InvoiceRecordInput:
    return InvoiceRecordInput(
        metadata=ReferenceMetadataInput(
            source="fixture",
            external_id=external_id,
            retention_until="2027-01-01",
        ),
        invoice=InvoiceReferenceInput(
            vendor_key=vendor_key,
            invoice_number=invoice_number,
            total="42.00",
            line_items=[
                ReferenceLineItemInput(
                    product_identifier="FICTIONAL-SERVICE",
                    total_price="42.00",
                )
            ],
        ),
    )


def test_create_invoice_returns_metadata_and_verification_facts(tmp_path) -> None:
    repository = _repository(tmp_path)

    created = repository.create_invoice(_record())

    assert len(created.metadata.record_id) == 32
    assert created.metadata.source == "fixture"
    assert created.metadata.external_id == "invoice-1"
    assert created.metadata.created_at == created.metadata.updated_at
    assert (
        repository.find_invoice("fictional-supplies", "INV-001")
        == created.invoice.to_domain()
    )


def test_create_invoice_rejects_duplicate_provenance(tmp_path) -> None:
    repository = _repository(tmp_path)
    repository.create_invoice(_record())

    with pytest.raises(ReferenceDataConflictError):
        repository.create_invoice(_record(invoice_number="INV-002"))

    assert repository.list_invoices(vendor_key=None, offset=0, limit=100).total == 1


def test_list_invoices_filters_and_paginates_in_stable_order(tmp_path) -> None:
    repository = _repository(tmp_path)
    first = repository.create_invoice(_record())
    second = repository.create_invoice(
        _record(external_id="invoice-2", invoice_number="INV-002")
    )
    repository.create_invoice(
        _record(
            external_id="invoice-3",
            vendor_key="other-vendor",
            invoice_number="INV-003",
        )
    )

    page = repository.list_invoices(vendor_key="fictional-supplies", offset=1, limit=1)

    assert page.total == 2
    assert [record.metadata.record_id for record in page.records] == [
        second.metadata.record_id
    ]
    assert first.metadata.record_id != second.metadata.record_id


def test_update_invoice_preserves_provenance_and_replaces_line_items(tmp_path) -> None:
    repository = _repository(tmp_path)
    created = repository.create_invoice(_record())
    update = InvoiceRecordUpdate(
        invoice=InvoiceReferenceInput(
            vendor_key="fictional-supplies",
            invoice_number="INV-UPDATED",
            total="84.00",
            line_items=[ReferenceLineItemInput(description="Updated item")],
        ),
        retention_until="2028-01-01",
    )

    updated = repository.update_admin_invoice(created.metadata.record_id, update)

    assert updated is not None
    assert updated.metadata.record_id == created.metadata.record_id
    assert updated.metadata.source == created.metadata.source
    assert updated.metadata.external_id == created.metadata.external_id
    assert updated.metadata.created_at == created.metadata.created_at
    assert updated.metadata.updated_at >= created.metadata.updated_at
    assert updated.metadata.retention_until.isoformat() == "2028-01-01"
    assert updated.invoice.invoice_number == "INV-UPDATED"
    assert [item.description for item in updated.invoice.line_items] == ["Updated item"]


def test_delete_invoice_cascades_line_items_and_reports_missing_records(
    tmp_path,
) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    repository = SQLiteInvoiceRepository(database_path)
    repository.initialize()
    created = repository.create_invoice(_record())

    assert repository.delete_admin_invoice(created.metadata.record_id) is True
    assert repository.get_admin_invoice(created.metadata.record_id) is None
    assert repository.delete_admin_invoice(created.metadata.record_id) is False

    with sqlite3.connect(database_path) as connection:
        line_item_count = connection.execute(
            "SELECT COUNT(*) FROM invoice_line_items"
        ).fetchone()[0]
    assert line_item_count == 0


def test_legacy_invoice_writes_receive_safe_administration_metadata(tmp_path) -> None:
    repository = _repository(tmp_path)
    repository.add_invoice(
        HistoricalInvoice(
            vendor_key="fictional-supplies",
            invoice_number="INV-LEGACY-API",
        )
    )

    page = repository.list_invoices(vendor_key=None, offset=0, limit=100)

    assert page.total == 1
    assert page.records[0].metadata.source == "application"
    assert page.records[0].metadata.external_id.startswith("invoice-")
