"""SQLite integration tests for managed invoice administration."""

import sqlite3
from decimal import Decimal
from typing import Any

import pytest

from veridoc.administration.models import (
    InvoiceRecordInput,
    InvoiceRecordUpdate,
    InvoiceReferenceInput,
    ReferenceLineItemInput,
    ReferenceMetadataInput,
)
from veridoc.administration.protocol import ReferenceDataConflictError
from veridoc.persistence import sqlite as sqlite_adapter
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


def test_list_invoices_uses_one_snapshot_for_count_and_records(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    reader = _repository(tmp_path)
    reader.create_invoice(_record())
    writer = SQLiteInvoiceRepository(database_path)
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA journal_mode = WAL").fetchone()[0] == "wal"

    second_created = False

    def create_second_invoice() -> None:
        nonlocal second_created
        if second_created:
            return
        second_created = True
        writer.create_invoice(
            _record(external_id="invoice-2", invoice_number="INV-002")
        )

    class CountCursorProxy:
        def __init__(self, cursor: sqlite3.Cursor) -> None:
            self._cursor = cursor

        def fetchone(self):
            row = self._cursor.fetchone()
            create_second_invoice()
            return row

        def __getattr__(self, name: str) -> Any:
            return getattr(self._cursor, name)

    class ConnectionProxy:
        def __init__(self, connection: sqlite3.Connection) -> None:
            self._connection = connection

        def execute(self, statement: str, parameters: tuple[object, ...] = ()):
            cursor = self._connection.execute(statement, parameters)
            if "SELECT COUNT(*) FROM vendor_invoices" in " ".join(statement.split()):
                return CountCursorProxy(cursor)
            return cursor

        def __enter__(self):
            self._connection.__enter__()
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return self._connection.__exit__(exc_type, exc_value, traceback)

        def close(self) -> None:
            self._connection.close()

    def coordinated_connection() -> ConnectionProxy:
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return ConnectionProxy(connection)

    monkeypatch.setattr(reader, "_connect", coordinated_connection)

    page = reader.list_invoices(vendor_key=None, offset=0, limit=100)

    assert second_created is True
    assert page.total == 1
    assert len(page.records) == 1


def test_get_invoice_uses_one_snapshot_for_header_and_line_items(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    reader = _repository(tmp_path)
    created = reader.create_invoice(_record())
    writer = SQLiteInvoiceRepository(database_path)
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("PRAGMA journal_mode = WAL").fetchone()[0] == "wal"

    original_line_items_from_rows = sqlite_adapter._line_items_from_rows
    updated = False

    def update_before_line_item_read(
        connection: sqlite3.Connection,
        table_name: str,
        parent_column: str,
        parent_id: int,
    ):
        nonlocal updated
        if table_name == "invoice_line_items" and not updated:
            updated = True
            writer.update_admin_invoice(
                created.metadata.record_id,
                InvoiceRecordUpdate(
                    invoice=InvoiceReferenceInput(
                        vendor_key="fictional-supplies",
                        invoice_number="INV-UPDATED",
                        total="84.00",
                        line_items=[
                            ReferenceLineItemInput(
                                description="Concurrent item",
                                total_price="84.00",
                            )
                        ],
                    ),
                    retention_until="2028-01-01",
                ),
            )
        return original_line_items_from_rows(
            connection, table_name, parent_column, parent_id
        )

    monkeypatch.setattr(
        sqlite_adapter, "_line_items_from_rows", update_before_line_item_read
    )

    observed = reader.get_admin_invoice(created.metadata.record_id)

    assert updated is True
    assert observed is not None
    assert observed.invoice.total == Decimal("42.00")
    assert observed.invoice.line_items[0].total_price == Decimal("42.00")


def test_update_invoice_preserves_provenance_and_replaces_line_items(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    repository = _repository(tmp_path)
    created = repository.create_invoice(_record())
    statements: list[str] = []

    def traced_connection() -> sqlite3.Connection:
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(repository, "_connect", traced_connection)
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
    assert statements[0] == "BEGIN IMMEDIATE"


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
