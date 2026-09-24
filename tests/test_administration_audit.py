"""Administration audit-log tests: migration, repository, routes, maintenance."""

from __future__ import annotations

import json
import sqlite3
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx
import pytest

from veridoc.administration.api import get_admin_repository
from veridoc.administration.models import AdminAuditEntryInput
from veridoc.app import app
from veridoc.persistence.migrations import migrate
from veridoc.persistence.schema import validate_current_schema
from veridoc.persistence.sqlite import (
    InvalidPersistedReferenceDataError,
    SQLiteInvoiceRepository,
    validate_persisted_reference_data,
)

_TOKEN = "phase-17-fixture-token-000000000000"
_AUTHORIZATION = {"Authorization": f"Bearer {_TOKEN}"}
_OCCURRED_AT = datetime(2026, 9, 24, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


def _repository(tmp_path) -> SQLiteInvoiceRepository:
    repository = SQLiteInvoiceRepository(tmp_path / "reference-data.sqlite")
    repository.initialize()
    return repository


def _context(request_id: str = "request-1"):
    from veridoc.administration.models import AdminAuditContext

    return AdminAuditContext(
        request_id=request_id, actor="admin", occurred_at=_OCCURRED_AT
    )


def _entry(
    *,
    operation="create",
    record_type="invoice",
    record_id="record-1",
    request_id="request-1",
    before_json=None,
    after_json='{"invoice_number": "INV-001"}',
) -> AdminAuditEntryInput:
    return AdminAuditEntryInput(
        occurred_at=_OCCURRED_AT,
        request_id=request_id,
        actor="admin",
        operation=operation,
        record_type=record_type,
        record_id=record_id,
        before_json=before_json,
        after_json=after_json,
    )


def test_migration_applies_the_audit_table_on_upgrade(tmp_path) -> None:
    """A version-5 database gains the audit table, indexes, and ledger row."""
    database_path = tmp_path / "reference-data.sqlite"
    with sqlite3.connect(database_path) as connection:
        migrate(connection)
        connection.execute("DELETE FROM schema_migrations WHERE version = 6")
        connection.execute("DROP TABLE admin_audit_log")
        connection.commit()
    with sqlite3.connect(database_path) as connection:
        migrate(connection, validate=validate_current_schema)
        versions = [
            row[0]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
        ]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }

    assert versions == [1, 2, 3, 4, 5, 6]
    assert "admin_audit_log" in tables
    assert "admin_audit_log_record_index" in indexes
    assert "admin_audit_log_occurred_at_index" in indexes


def test_audit_round_trip_assigns_sequence_identifiers(tmp_path) -> None:
    """Recorded entries return with stable identifiers in insertion order."""
    repository = _repository(tmp_path)

    first = repository.record_admin_action(_entry(record_id="record-1"))
    second = repository.record_admin_action(_entry(record_id="record-2"))

    assert first.entry_id == 1
    assert second.entry_id == 2
    assert first.occurred_at == _OCCURRED_AT
    assert first.request_id == "request-1"
    assert first.actor == "admin"
    page = repository.list_admin_audit_log(
        record_type=None, record_id=None, offset=0, limit=200
    )
    assert page.total == 2
    assert [entry.entry_id for entry in page.records] == [1, 2]


def test_audit_listing_filters_and_paginates(tmp_path) -> None:
    """Type and record filters scope the log; offset and limit page it."""
    repository = _repository(tmp_path)
    repository.record_admin_action(_entry(record_type="invoice", record_id="a"))
    repository.record_admin_action(_entry(record_type="vendor", record_id="b"))
    repository.record_admin_action(_entry(record_type="invoice", record_id="c"))

    by_type = repository.list_admin_audit_log(
        record_type="invoice", record_id=None, offset=0, limit=200
    )
    by_record = repository.list_admin_audit_log(
        record_type=None, record_id="b", offset=0, limit=200
    )
    page = repository.list_admin_audit_log(
        record_type=None, record_id=None, offset=1, limit=1
    )

    assert [entry.record_id for entry in by_type.records] == ["a", "c"]
    assert [entry.record_id for entry in by_record.records] == ["b"]
    assert page.total == 3
    assert [entry.record_id for entry in page.records] == ["b"]


def test_audit_listing_is_empty_without_entries(tmp_path) -> None:
    """An untouched store reports an empty audit page."""
    repository = _repository(tmp_path)
    page = repository.list_admin_audit_log(
        record_type=None, record_id=None, offset=0, limit=200
    )

    assert page.records == []
    assert page.total == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("operation", "destroy"),
        ("record_type", "receipt"),
        ("actor", "reviewer-1"),
        ("request_id", "x" * 129),
        ("after_json", "[1, 2, 3]"),
    ],
)
def test_audit_row_validation_rejects_malformed_persisted_rows(
    tmp_path, field: str, value: str
) -> None:
    """Malformed audit rows fail maintenance validation like other rows."""
    repository = _repository(tmp_path)
    stored = repository.record_admin_action(_entry())
    assert stored.entry_id == 1
    database_path = tmp_path / "reference-data.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            f"UPDATE admin_audit_log SET {field} = ? WHERE id = 1", (value,)
        )
        connection.commit()
        with pytest.raises(InvalidPersistedReferenceDataError):
            validate_persisted_reference_data(connection)


@asynccontextmanager
async def _client(repository: SQLiteInvoiceRepository):
    app.dependency_overrides[get_admin_repository] = lambda: repository
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def _invoice_payload(
    *, external_id: str = "invoice-1", invoice_number: str = "INV-001"
) -> dict:
    return {
        "metadata": {"source": "fixture", "external_id": external_id},
        "invoice": {
            "vendor_key": "fictional-supplies",
            "invoice_number": invoice_number,
            "currency": "USD",
            "total": "42.00",
        },
    }


@pytest.mark.anyio
async def test_invoice_lifecycle_writes_linked_audit_entries(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invoice create, update, and delete each log one linked entry."""
    repository = _repository(tmp_path)
    monkeypatch.setenv("VERIDOC_ADMIN_TOKEN", _TOKEN)
    async with _client(repository) as client:
        created = await client.post(
            "/admin/reference-data/invoices",
            headers={**_AUTHORIZATION, "X-Request-ID": "trace-create"},
            json=_invoice_payload(),
        )
        assert created.status_code == 201
        record_id = created.json()["metadata"]["record_id"]
        updated = await client.put(
            f"/admin/reference-data/invoices/{record_id}",
            headers={**_AUTHORIZATION, "X-Request-ID": "trace-update"},
            json={
                "invoice": {
                    "vendor_key": "fictional-supplies",
                    "invoice_number": "INV-002",
                }
            },
        )
        assert updated.status_code == 200
        deleted = await client.delete(
            f"/admin/reference-data/invoices/{record_id}",
            headers={**_AUTHORIZATION, "X-Request-ID": "trace-delete"},
        )
        assert deleted.status_code == 204

    page = repository.list_admin_audit_log(
        record_type="invoice", record_id=record_id, offset=0, limit=200
    )
    assert [(entry.operation, entry.request_id) for entry in page.records] == [
        ("create", "trace-create"),
        ("update", "trace-update"),
        ("delete", "trace-delete"),
    ]
    assert page.records[0].before_json is None
    assert (
        json.loads(page.records[0].after_json or "{}")["invoice"]["invoice_number"]
        == "INV-001"
    )
    assert (
        json.loads(page.records[1].before_json or "{}")["invoice"]["invoice_number"]
        == "INV-001"
    )
    assert (
        json.loads(page.records[1].after_json or "{}")["invoice"]["invoice_number"]
        == "INV-002"
    )
    assert (
        json.loads(page.records[2].before_json or "{}")["invoice"]["invoice_number"]
        == "INV-002"
    )
    assert page.records[2].after_json is None


@pytest.mark.anyio
async def test_failed_mutations_write_no_audit_entries(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unknown-record and conflict failures leave the log untouched."""
    repository = _repository(tmp_path)
    monkeypatch.setenv("VERIDOC_ADMIN_TOKEN", _TOKEN)
    async with _client(repository) as client:
        missing = await client.put(
            "/admin/reference-data/invoices/missing-record",
            headers=_AUTHORIZATION,
            json={
                "invoice": {
                    "vendor_key": "fictional-supplies",
                    "invoice_number": "INV-002",
                }
            },
        )
        assert missing.status_code == 404
        await client.post(
            "/admin/reference-data/invoices",
            headers=_AUTHORIZATION,
            json=_invoice_payload(),
        )
        conflict = await client.post(
            "/admin/reference-data/invoices",
            headers=_AUTHORIZATION,
            json=_invoice_payload(),
        )
        assert conflict.status_code == 409

    page = repository.list_admin_audit_log(
        record_type=None, record_id=None, offset=0, limit=200
    )
    assert page.total == 1
    assert page.records[0].operation == "create"


@pytest.mark.anyio
async def test_purchase_order_and_vendor_creates_write_entries(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Purchase-order and vendor creates log with their own record types."""
    repository = _repository(tmp_path)
    monkeypatch.setenv("VERIDOC_ADMIN_TOKEN", _TOKEN)
    async with _client(repository) as client:
        purchase_order = await client.post(
            "/admin/reference-data/purchase-orders",
            headers={**_AUTHORIZATION, "X-Request-ID": "trace-po"},
            json={
                "metadata": {"source": "fixture", "external_id": "purchase-order-1"},
                "purchase_order": {
                    "vendor_key": "fictional-supplies",
                    "purchase_order_number": "PO-001",
                    "currency": "USD",
                    "total": "42.00",
                },
            },
        )
        assert purchase_order.status_code == 201
        vendor = await client.post(
            "/admin/reference-data/vendors",
            headers={**_AUTHORIZATION, "X-Request-ID": "trace-vendor"},
            json={
                "metadata": {"source": "fixture", "external_id": "vendor-1"},
                "vendor": {
                    "vendor_id": "vnd_001",
                    "legal_name": "Acme Supplies Corp",
                    "canonical_key": "acme-supplies",
                    "status": "active",
                },
            },
        )
        assert vendor.status_code == 201

    page = repository.list_admin_audit_log(
        record_type=None, record_id=None, offset=0, limit=200
    )
    assert [(entry.record_type, entry.request_id) for entry in page.records] == [
        ("purchase_order", "trace-po"),
        ("vendor", "trace-vendor"),
    ]


@pytest.mark.anyio
async def test_import_writes_per_record_entries_and_dry_run_writes_none(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Applied imports log one entry per record; dry runs log nothing."""
    repository = _repository(tmp_path)
    monkeypatch.setenv("VERIDOC_ADMIN_TOKEN", _TOKEN)
    batch = {
        "invoices": [_invoice_payload()],
        "purchase_orders": [],
        "vendors": [],
    }
    async with _client(repository) as client:
        dry_run = await client.post(
            "/admin/reference-data/import?dry_run=true",
            headers={**_AUTHORIZATION, "X-Request-ID": "trace-dry"},
            files={
                "file": (
                    "batch.json",
                    json.dumps(batch).encode("utf-8"),
                    "application/json",
                )
            },
        )
        assert dry_run.status_code == 200
        applied = await client.post(
            "/admin/reference-data/import",
            headers={**_AUTHORIZATION, "X-Request-ID": "trace-import"},
            files={
                "file": (
                    "batch.json",
                    json.dumps(batch).encode("utf-8"),
                    "application/json",
                )
            },
        )
        assert applied.status_code == 200

    page = repository.list_admin_audit_log(
        record_type=None, record_id=None, offset=0, limit=200
    )
    assert [(entry.operation, entry.request_id) for entry in page.records] == [
        ("import", "trace-import")
    ]


@pytest.mark.anyio
async def test_backup_and_restore_preserve_audit_entries(tmp_path) -> None:
    """The audit log travels with the database that owns it."""
    from veridoc.persistence.maintenance import backup_database, restore_database

    repository = _repository(tmp_path)
    stored = repository.record_admin_action(_entry(request_id="trace-keep"))
    backup_path = tmp_path / "reference-data.backup.sqlite"
    restored_path = tmp_path / "reference-data.restored.sqlite"

    backup_database(tmp_path / "reference-data.sqlite", backup_path)
    restore_database(backup_path, restored_path)

    restored = SQLiteInvoiceRepository(restored_path)
    restored.initialize()
    page = restored.list_admin_audit_log(
        record_type=None, record_id=None, offset=0, limit=200
    )
    assert [entry.request_id for entry in page.records] == ["trace-keep"]
    assert stored.entry_id == page.records[0].entry_id
