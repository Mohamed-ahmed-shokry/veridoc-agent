"""SQLite backup and restore safety tests."""

import sqlite3
from pathlib import Path

import pytest

from veridoc.persistence.maintenance import (
    ReferenceDataMaintenanceError,
    backup_database,
    restore_database,
)
from veridoc.persistence.migrations import LATEST_SCHEMA_VERSION
from veridoc.persistence.sqlite import SQLiteInvoiceRepository
from veridoc.verification.references import HistoricalInvoice


def _repository(path) -> SQLiteInvoiceRepository:
    repository = SQLiteInvoiceRepository(path)
    repository.initialize()
    return repository


def _add_invoice(repository: SQLiteInvoiceRepository, number: str) -> None:
    repository.add_invoice(
        HistoricalInvoice(vendor_key="fictional-supplies", invoice_number=number)
    )


def _add_orphaned_line_item(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO invoice_line_items (invoice_id, position)
            VALUES (999, 0)
            """
        )


def test_backup_creates_an_integrity_checked_independent_database(tmp_path) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    backup_path = tmp_path / "backups" / "reference-data.backup.sqlite"
    repository = _repository(database_path)
    _add_invoice(repository, "INV-001")

    result = backup_database(database_path, backup_path)
    _add_invoice(repository, "INV-002")
    backup_repository = _repository(backup_path)

    assert result == backup_path.resolve()
    assert [
        invoice.invoice_number
        for invoice in backup_repository.list_vendor_invoices("fictional-supplies")
    ] == ["INV-001"]


def test_backup_preserves_a_legacy_source_and_pre_upgrade_snapshot(tmp_path) -> None:
    database_path = tmp_path / "legacy-reference-data.sqlite"
    backup_path = tmp_path / "legacy-reference-data.backup.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE vendor_invoices (
                id INTEGER PRIMARY KEY,
                vendor_key TEXT NOT NULL,
                invoice_number TEXT,
                purchase_order_number TEXT,
                invoice_date TEXT,
                due_date TEXT,
                currency TEXT,
                subtotal TEXT,
                tax TEXT,
                discount TEXT,
                total TEXT,
                payment_terms TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO vendor_invoices (vendor_key, invoice_number)
            VALUES ('fictional-supplies', 'INV-LEGACY')
            """
        )
    original_source = database_path.read_bytes()

    backup_database(database_path, backup_path)

    assert database_path.read_bytes() == original_source
    for path in (database_path, backup_path):
        with sqlite3.connect(path) as connection:
            table_names = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(vendor_invoices)")
            }
        assert "schema_migrations" not in table_names
        assert "record_id" not in columns

    restored_path = tmp_path / "restored-reference-data.sqlite"
    restore_database(backup_path, restored_path)
    restored = _repository(restored_path)
    assert restored.find_invoice("fictional-supplies", "INV-LEGACY") is not None


def test_restore_atomically_replaces_target_and_migrates_the_backup(tmp_path) -> None:
    backup_path = tmp_path / "legacy-backup.sqlite"
    database_path = tmp_path / "reference-data.sqlite"
    with sqlite3.connect(backup_path) as connection:
        connection.execute(
            """
            CREATE TABLE vendor_invoices (
                id INTEGER PRIMARY KEY,
                vendor_key TEXT NOT NULL,
                invoice_number TEXT,
                purchase_order_number TEXT,
                invoice_date TEXT,
                due_date TEXT,
                currency TEXT,
                subtotal TEXT,
                tax TEXT,
                discount TEXT,
                total TEXT,
                payment_terms TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO vendor_invoices (vendor_key, invoice_number)
            VALUES ('fictional-supplies', 'INV-BACKUP')
            """
        )

    target_repository = _repository(database_path)
    _add_invoice(target_repository, "INV-REPLACED")

    result = restore_database(backup_path, database_path)
    restored = _repository(database_path)

    assert result == database_path.resolve()
    assert [
        invoice.invoice_number
        for invoice in restored.list_vendor_invoices("fictional-supplies")
    ] == ["INV-BACKUP"]
    with sqlite3.connect(database_path) as connection:
        latest = connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0]
    assert latest == LATEST_SCHEMA_VERSION


def test_failed_restore_preserves_the_existing_database(tmp_path) -> None:
    backup_path = tmp_path / "corrupt-backup.sqlite"
    backup_path.write_bytes(b"not a SQLite database")
    database_path = tmp_path / "reference-data.sqlite"
    repository = _repository(database_path)
    _add_invoice(repository, "INV-KEEP")

    with pytest.raises(ReferenceDataMaintenanceError):
        restore_database(backup_path, database_path)

    preserved = _repository(database_path)
    assert preserved.find_invoice("fictional-supplies", "INV-KEEP") is not None


def test_backup_rejects_an_incomplete_current_schema(tmp_path) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    backup_path = tmp_path / "reference-data.backup.sqlite"
    _repository(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("DROP TABLE purchase_order_line_items")

    with pytest.raises(ReferenceDataMaintenanceError):
        backup_database(database_path, backup_path)

    assert not backup_path.exists()


def test_restore_rejects_an_incomplete_current_schema(tmp_path) -> None:
    backup_path = tmp_path / "incomplete-backup.sqlite"
    _repository(backup_path)
    with sqlite3.connect(backup_path) as connection:
        connection.execute("DROP TABLE purchase_order_line_items")
    database_path = tmp_path / "reference-data.sqlite"
    repository = _repository(database_path)
    _add_invoice(repository, "INV-KEEP")

    with pytest.raises(ReferenceDataMaintenanceError):
        restore_database(backup_path, database_path)

    preserved = _repository(database_path)
    assert preserved.find_invoice("fictional-supplies", "INV-KEEP") is not None


def test_backup_rejects_a_missing_unique_index(tmp_path) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    backup_path = tmp_path / "reference-data.backup.sqlite"
    _repository(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("DROP INDEX purchase_orders_source_external_id_index")

    with pytest.raises(ReferenceDataMaintenanceError):
        backup_database(database_path, backup_path)

    assert not backup_path.exists()


def test_restore_rejects_a_missing_foreign_key_and_preserves_target(tmp_path) -> None:
    backup_path = tmp_path / "invalid-backup.sqlite"
    _repository(backup_path)
    with sqlite3.connect(backup_path) as connection:
        connection.execute("DROP TABLE invoice_line_items")
        connection.execute(
            """
            CREATE TABLE invoice_line_items (
                id INTEGER PRIMARY KEY,
                invoice_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                description TEXT,
                product_identifier TEXT,
                quantity TEXT,
                unit_price TEXT,
                total_price TEXT
            )
            """
        )
    database_path = tmp_path / "reference-data.sqlite"
    repository = _repository(database_path)
    _add_invoice(repository, "INV-KEEP")

    with pytest.raises(ReferenceDataMaintenanceError):
        restore_database(backup_path, database_path)

    preserved = _repository(database_path)
    assert preserved.find_invoice("fictional-supplies", "INV-KEEP") is not None


def test_backup_rejects_foreign_key_corruption(tmp_path) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    backup_path = tmp_path / "reference-data.backup.sqlite"
    _repository(database_path)
    _add_orphaned_line_item(database_path)

    with pytest.raises(ReferenceDataMaintenanceError):
        backup_database(database_path, backup_path)

    assert not backup_path.exists()


def test_restore_rejects_foreign_key_corruption_and_preserves_target(tmp_path) -> None:
    backup_path = tmp_path / "corrupt-backup.sqlite"
    _repository(backup_path)
    _add_orphaned_line_item(backup_path)
    database_path = tmp_path / "reference-data.sqlite"
    repository = _repository(database_path)
    _add_invoice(repository, "INV-KEEP")

    with pytest.raises(ReferenceDataMaintenanceError):
        restore_database(backup_path, database_path)

    preserved = _repository(database_path)
    assert preserved.find_invoice("fictional-supplies", "INV-KEEP") is not None


def test_maintenance_rejects_missing_and_same_paths(tmp_path) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    _repository(database_path)

    with pytest.raises(ReferenceDataMaintenanceError):
        backup_database(tmp_path / "missing.sqlite", tmp_path / "backup.sqlite")
    with pytest.raises(ReferenceDataMaintenanceError):
        backup_database(database_path, database_path)


@pytest.mark.parametrize("operation", [backup_database, restore_database])
@pytest.mark.parametrize("sidecar_suffix", ["-wal", "-shm", "-journal"])
def test_maintenance_rejects_destination_sidecars_without_replacement(
    operation,
    sidecar_suffix: str,
    tmp_path,
) -> None:
    source_path = tmp_path / "source.sqlite"
    source_repository = _repository(source_path)
    _add_invoice(source_repository, "INV-SOURCE")

    destination_path = tmp_path / "destination.sqlite"
    destination_repository = _repository(destination_path)
    _add_invoice(destination_repository, "INV-KEEP")
    original_destination = destination_path.read_bytes()
    sidecar_path = Path(f"{destination_path}{sidecar_suffix}")
    sidecar_path.touch()

    with pytest.raises(ReferenceDataMaintenanceError):
        operation(source_path, destination_path)

    assert destination_path.read_bytes() == original_destination
    assert sidecar_path.exists()
