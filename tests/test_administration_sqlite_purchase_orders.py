"""SQLite integration tests for managed purchase-order administration."""

import sqlite3

import pytest

from veridoc.administration.models import (
    PurchaseOrderRecordInput,
    PurchaseOrderRecordUpdate,
    PurchaseOrderReferenceInput,
    ReferenceLineItemInput,
    ReferenceMetadataInput,
)
from veridoc.administration.protocol import ReferenceDataConflictError
from veridoc.persistence.sqlite import SQLiteInvoiceRepository
from veridoc.verification.references import PurchaseOrder


def _repository(tmp_path) -> SQLiteInvoiceRepository:
    repository = SQLiteInvoiceRepository(tmp_path / "reference-data.sqlite")
    repository.initialize()
    return repository


def _record(
    *,
    external_id: str = "purchase-order-1",
    vendor_key: str = "fictional-supplies",
    purchase_order_number: str = "PO-001",
) -> PurchaseOrderRecordInput:
    return PurchaseOrderRecordInput(
        metadata=ReferenceMetadataInput(
            source="fixture",
            external_id=external_id,
            retention_until="2027-01-01",
        ),
        purchase_order=PurchaseOrderReferenceInput(
            vendor_key=vendor_key,
            purchase_order_number=purchase_order_number,
            total="42.00",
            line_items=[
                ReferenceLineItemInput(
                    product_identifier="FICTIONAL-SERVICE",
                    total_price="42.00",
                )
            ],
        ),
    )


def test_create_purchase_order_returns_metadata_and_verification_facts(
    tmp_path,
) -> None:
    repository = _repository(tmp_path)

    created = repository.create_purchase_order(_record())

    assert len(created.metadata.record_id) == 32
    assert created.metadata.source == "fixture"
    assert created.metadata.external_id == "purchase-order-1"
    assert created.metadata.created_at == created.metadata.updated_at
    assert (
        repository.get_purchase_order("fictional-supplies", "PO-001")
        == created.purchase_order.to_domain()
    )


def test_create_purchase_order_rejects_provenance_and_natural_key_conflicts(
    tmp_path,
) -> None:
    repository = _repository(tmp_path)
    repository.create_purchase_order(_record())

    with pytest.raises(ReferenceDataConflictError):
        repository.create_purchase_order(_record(external_id="purchase-order-2"))

    with pytest.raises(ReferenceDataConflictError):
        repository.create_purchase_order(
            _record(
                external_id="purchase-order-1",
                purchase_order_number="PO-002",
            )
        )

    page = repository.list_purchase_orders(vendor_key=None, offset=0, limit=100)
    assert page.total == 1


def test_list_purchase_orders_filters_and_paginates_in_stable_order(
    tmp_path,
) -> None:
    repository = _repository(tmp_path)
    first = repository.create_purchase_order(_record())
    second = repository.create_purchase_order(
        _record(
            external_id="purchase-order-2",
            purchase_order_number="PO-002",
        )
    )
    repository.create_purchase_order(
        _record(
            external_id="purchase-order-3",
            vendor_key="other-vendor",
            purchase_order_number="PO-003",
        )
    )

    page = repository.list_purchase_orders(
        vendor_key="fictional-supplies", offset=1, limit=1
    )

    assert page.total == 2
    assert [record.metadata.record_id for record in page.records] == [
        second.metadata.record_id
    ]
    assert first.metadata.record_id != second.metadata.record_id


def test_update_purchase_order_preserves_provenance_and_replaces_line_items(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    repository = _repository(tmp_path)
    created = repository.create_purchase_order(_record())
    statements: list[str] = []

    def traced_connection() -> sqlite3.Connection:
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(repository, "_connect", traced_connection)
    update = PurchaseOrderRecordUpdate(
        purchase_order=PurchaseOrderReferenceInput(
            vendor_key="fictional-supplies",
            purchase_order_number="PO-UPDATED",
            total="84.00",
            line_items=[ReferenceLineItemInput(description="Updated item")],
        ),
        retention_until="2028-01-01",
    )

    updated = repository.update_admin_purchase_order(created.metadata.record_id, update)

    assert updated is not None
    assert updated.metadata.record_id == created.metadata.record_id
    assert updated.metadata.source == created.metadata.source
    assert updated.metadata.external_id == created.metadata.external_id
    assert updated.metadata.created_at == created.metadata.created_at
    assert updated.metadata.updated_at >= created.metadata.updated_at
    assert updated.metadata.retention_until.isoformat() == "2028-01-01"
    assert updated.purchase_order.purchase_order_number == "PO-UPDATED"
    assert [item.description for item in updated.purchase_order.line_items] == [
        "Updated item"
    ]
    assert statements[0] == "BEGIN IMMEDIATE"


def test_delete_purchase_order_cascades_line_items_and_reports_missing_records(
    tmp_path,
) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    repository = SQLiteInvoiceRepository(database_path)
    repository.initialize()
    created = repository.create_purchase_order(_record())

    assert repository.delete_admin_purchase_order(created.metadata.record_id) is True
    assert repository.get_admin_purchase_order(created.metadata.record_id) is None
    assert repository.delete_admin_purchase_order(created.metadata.record_id) is False

    with sqlite3.connect(database_path) as connection:
        line_item_count = connection.execute(
            "SELECT COUNT(*) FROM purchase_order_line_items"
        ).fetchone()[0]
    assert line_item_count == 0


def test_legacy_purchase_order_writes_receive_administration_metadata(
    tmp_path,
) -> None:
    repository = _repository(tmp_path)
    repository.add_purchase_order(
        PurchaseOrder(
            vendor_key="fictional-supplies",
            purchase_order_number="PO-LEGACY-API",
        )
    )

    page = repository.list_purchase_orders(vendor_key=None, offset=0, limit=100)

    assert page.total == 1
    assert page.records[0].metadata.source == "application"
    assert page.records[0].metadata.external_id.startswith("purchase-order-")
