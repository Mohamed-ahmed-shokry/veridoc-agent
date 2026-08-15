"""SQLite backup and restore safety tests."""

import sqlite3
from pathlib import Path

import pytest

from veridoc.persistence import maintenance
from veridoc.persistence.maintenance import (
    ReferenceDataMaintenanceError,
    backup_database,
    restore_database,
)
from veridoc.persistence.migrations import LATEST_SCHEMA_VERSION
from veridoc.persistence.sqlite import (
    InvalidPersistedReferenceDataError,
    SQLiteInvoiceRepository,
)
from veridoc.verification.references import HistoricalInvoice, ReferenceLineItem


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


def _corrupt_invoice_line_item(path: Path, repository: SQLiteInvoiceRepository) -> None:
    repository.add_invoice(
        HistoricalInvoice(
            vendor_key="fictional-supplies",
            invoice_number="INV-CORRUPT-CHILD",
            line_items=[ReferenceLineItem(quantity="2")],
        )
    )
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE invoice_line_items SET quantity = 'not-a-decimal'")


def _add_noncanonical_invoice_line_item_position(
    path: Path, repository: SQLiteInvoiceRepository, position: int
) -> None:
    repository.add_invoice(
        HistoricalInvoice(
            vendor_key="fictional-supplies",
            invoice_number="INV-NONCANONICAL-POSITION",
            line_items=[ReferenceLineItem(quantity="2")],
        )
    )
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO invoice_line_items (invoice_id, position)
            SELECT id, ? FROM vendor_invoices WHERE invoice_number = ?
            """,
            (position, "INV-NONCANONICAL-POSITION"),
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


@pytest.mark.parametrize("operation", [backup_database, restore_database])
def test_maintenance_validates_migrations_before_commit(
    operation,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "legacy-reference-data.sqlite"
    destination_path = tmp_path / "validated-reference-data.sqlite"
    with sqlite3.connect(source_path) as connection:
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
    original_validator = maintenance.validate_current_schema
    transaction_states: list[bool] = []

    def validate_in_transaction(connection: sqlite3.Connection) -> None:
        transaction_states.append(connection.in_transaction)
        original_validator(connection)

    monkeypatch.setattr(
        maintenance,
        "validate_current_schema",
        validate_in_transaction,
    )

    operation(source_path, destination_path)

    assert transaction_states == [True]


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


@pytest.mark.parametrize("operation", [backup_database, restore_database])
def test_maintenance_rejects_an_altered_unique_index_predicate(
    operation,
    tmp_path,
) -> None:
    source_path = tmp_path / "source.sqlite"
    _repository(source_path)
    with sqlite3.connect(source_path) as connection:
        connection.execute("DROP INDEX vendor_invoices_source_external_id_index")
        connection.execute(
            """
            CREATE UNIQUE INDEX vendor_invoices_source_external_id_index
            ON vendor_invoices(source, external_id)
            WHERE source IS NOT NULL
            """
        )
    destination_path = tmp_path / "destination.sqlite"
    destination_repository = _repository(destination_path)
    _add_invoice(destination_repository, "INV-KEEP")
    original_destination = destination_path.read_bytes()

    with pytest.raises(ReferenceDataMaintenanceError):
        operation(source_path, destination_path)

    assert destination_path.read_bytes() == original_destination


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


@pytest.mark.parametrize("operation", [backup_database, restore_database])
def test_maintenance_rejects_managed_table_triggers_without_replacement(
    operation,
    tmp_path,
) -> None:
    source_path = tmp_path / "triggered-legacy.sqlite"
    with sqlite3.connect(source_path) as connection:
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
            VALUES ('fictional-supplies', 'INV-TRIGGERED')
            """
        )
        connection.execute(
            """
            CREATE TRIGGER delete_invoice_after_update
            AFTER UPDATE ON vendor_invoices
            BEGIN
                DELETE FROM vendor_invoices WHERE id = NEW.id;
            END
            """
        )

    destination_path = tmp_path / "reference-data.sqlite"
    destination = _repository(destination_path)
    _add_invoice(destination, "INV-KEEP")

    with pytest.raises(ReferenceDataMaintenanceError):
        operation(source_path, destination_path)

    preserved = _repository(destination_path)
    assert preserved.find_invoice("fictional-supplies", "INV-KEEP") is not None
    with sqlite3.connect(source_path) as connection:
        source_invoice = connection.execute(
            "SELECT invoice_number FROM vendor_invoices"
        ).fetchone()
    assert source_invoice == ("INV-TRIGGERED",)


def test_backup_rejects_foreign_key_corruption(tmp_path) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    backup_path = tmp_path / "reference-data.backup.sqlite"
    _repository(database_path)
    _add_orphaned_line_item(database_path)

    with pytest.raises(ReferenceDataMaintenanceError):
        backup_database(database_path, backup_path)

    assert not backup_path.exists()


def test_backup_rejects_semantic_corruption_without_replacement(tmp_path) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    repository = _repository(database_path)
    _corrupt_invoice_line_item(database_path, repository)
    backup_path = tmp_path / "reference-data.backup.sqlite"
    backup_repository = _repository(backup_path)
    _add_invoice(backup_repository, "INV-KEEP")
    original_source = database_path.read_bytes()
    original_destination = backup_path.read_bytes()

    with pytest.raises(ReferenceDataMaintenanceError) as error:
        backup_database(database_path, backup_path)

    assert isinstance(error.value.__cause__, InvalidPersistedReferenceDataError)
    assert database_path.read_bytes() == original_source
    assert backup_path.read_bytes() == original_destination
    assert list(tmp_path.glob(f".{backup_path.name}.*.tmp")) == []


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


def test_restore_rejects_semantic_corruption_without_replacement(tmp_path) -> None:
    backup_path = tmp_path / "reference-data.backup.sqlite"
    backup_repository = _repository(backup_path)
    _corrupt_invoice_line_item(backup_path, backup_repository)
    database_path = tmp_path / "reference-data.sqlite"
    repository = _repository(database_path)
    _add_invoice(repository, "INV-KEEP")
    original_source = backup_path.read_bytes()
    original_destination = database_path.read_bytes()

    with pytest.raises(ReferenceDataMaintenanceError) as error:
        restore_database(backup_path, database_path)

    assert isinstance(error.value.__cause__, InvalidPersistedReferenceDataError)
    assert backup_path.read_bytes() == original_source
    assert database_path.read_bytes() == original_destination
    assert list(tmp_path.glob(f".{database_path.name}.*.tmp")) == []


@pytest.mark.parametrize("operation", [backup_database, restore_database])
@pytest.mark.parametrize("position", [-1, 2])
def test_maintenance_rejects_noncanonical_line_item_positions(
    operation, position: int, tmp_path
) -> None:
    source_path = tmp_path / "source.sqlite"
    source_repository = _repository(source_path)
    _add_noncanonical_invoice_line_item_position(
        source_path, source_repository, position
    )
    destination_path = tmp_path / "destination.sqlite"
    destination_repository = _repository(destination_path)
    _add_invoice(destination_repository, "INV-KEEP")
    original_source = source_path.read_bytes()
    original_destination = destination_path.read_bytes()

    with pytest.raises(ReferenceDataMaintenanceError) as error:
        operation(source_path, destination_path)

    assert isinstance(error.value.__cause__, InvalidPersistedReferenceDataError)
    assert source_path.read_bytes() == original_source
    assert destination_path.read_bytes() == original_destination
    assert list(tmp_path.glob(f".{destination_path.name}.*.tmp")) == []


def test_maintenance_rejects_missing_and_same_paths(tmp_path) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    _repository(database_path)

    with pytest.raises(ReferenceDataMaintenanceError):
        backup_database(tmp_path / "missing.sqlite", tmp_path / "backup.sqlite")
    with pytest.raises(ReferenceDataMaintenanceError):
        backup_database(database_path, database_path)


@pytest.mark.parametrize("operation", [backup_database, restore_database])
@pytest.mark.parametrize("resolution_exception", [OSError, RuntimeError])
def test_maintenance_maps_path_resolution_failures(
    operation,
    resolution_exception,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "source.sqlite"
    _repository(source_path)
    destination_path = tmp_path / "destination.sqlite"
    original_resolve = maintenance.Path.resolve

    def fail_source_resolution(path: Path, *args, **kwargs) -> Path:
        if path == source_path:
            raise resolution_exception("synthetic resolution failure")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(maintenance.Path, "resolve", fail_source_resolution)

    with pytest.raises(ReferenceDataMaintenanceError) as error:
        operation(source_path, destination_path)

    assert isinstance(error.value.__cause__, resolution_exception)
    assert not destination_path.exists()


@pytest.mark.parametrize("operation", [backup_database, restore_database])
def test_maintenance_maps_temporary_cleanup_failures(
    operation,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "source.sqlite"
    source_repository = _repository(source_path)
    _add_invoice(source_repository, "INV-SOURCE")
    destination_path = tmp_path / "destination.sqlite"
    destination_repository = _repository(destination_path)
    _add_invoice(destination_repository, "INV-KEEP")
    original_destination = destination_path.read_bytes()
    temporary_paths = [
        tmp_path / "temporary.sqlite",
        tmp_path / "validation-temporary.sqlite",
    ]
    temporary_path_iterator = iter(temporary_paths)

    def create_temporary_sibling(destination: Path) -> Path:
        del destination
        path = next(temporary_path_iterator)
        path.touch()
        return path

    def fail_integrity(connection: sqlite3.Connection) -> None:
        del connection
        raise ReferenceDataMaintenanceError

    original_unlink = maintenance.Path.unlink

    def deny_first_temporary_cleanup(path: Path, *, missing_ok: bool = False) -> None:
        if path == temporary_paths[0]:
            raise PermissionError("synthetic cleanup failure")
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(
        maintenance,
        "_temporary_sibling",
        create_temporary_sibling,
    )
    monkeypatch.setattr(maintenance, "_validate_integrity", fail_integrity)
    monkeypatch.setattr(
        maintenance.Path,
        "unlink",
        deny_first_temporary_cleanup,
    )

    with pytest.raises(ReferenceDataMaintenanceError) as error:
        operation(source_path, destination_path)

    assert isinstance(error.value.__cause__, PermissionError)
    assert destination_path.read_bytes() == original_destination
    assert not temporary_paths[1].exists()
    original_unlink(temporary_paths[0], missing_ok=True)


@pytest.mark.parametrize("operation", [backup_database, restore_database])
def test_maintenance_does_not_recreate_a_source_removed_after_validation(
    operation,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "source.sqlite"
    source_repository = _repository(source_path)
    _add_invoice(source_repository, "INV-SOURCE")
    destination_path = tmp_path / "destination.sqlite"
    destination_repository = _repository(destination_path)
    _add_invoice(destination_repository, "INV-KEEP")
    original_destination = destination_path.read_bytes()
    require_source = maintenance._require_distinct_existing_source

    def remove_source_after_validation(source: Path, destination: Path) -> None:
        require_source(source, destination)
        source.unlink()

    monkeypatch.setattr(
        maintenance,
        "_require_distinct_existing_source",
        remove_source_after_validation,
    )

    with pytest.raises(ReferenceDataMaintenanceError):
        operation(source_path, destination_path)

    assert not source_path.exists()
    assert destination_path.read_bytes() == original_destination
    assert list(tmp_path.glob(f".{destination_path.name}.*.tmp")) == []


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


@pytest.mark.parametrize("operation", [backup_database, restore_database])
@pytest.mark.parametrize("sidecar_suffix", ["-wal", "-shm", "-journal"])
def test_maintenance_rejects_destination_sidecars_created_before_publication(
    operation,
    sidecar_suffix: str,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "source.sqlite"
    source_repository = _repository(source_path)
    _add_invoice(source_repository, "INV-SOURCE")
    destination_path = tmp_path / "destination.sqlite"
    destination_repository = _repository(destination_path)
    _add_invoice(destination_repository, "INV-KEEP")
    original_destination = destination_path.read_bytes()
    sidecar_path = Path(f"{destination_path}{sidecar_suffix}")
    original_guard = maintenance._require_no_live_sidecars
    destination_checks = 0

    def create_sidecar_before_final_destination_guard(path: Path) -> None:
        nonlocal destination_checks
        if path == destination_path:
            destination_checks += 1
            if destination_checks == 2:
                sidecar_path.touch()
        original_guard(path)

    monkeypatch.setattr(
        maintenance,
        "_require_no_live_sidecars",
        create_sidecar_before_final_destination_guard,
    )

    with pytest.raises(ReferenceDataMaintenanceError):
        operation(source_path, destination_path)

    assert destination_path.read_bytes() == original_destination
    assert sidecar_path.exists()
    assert list(tmp_path.glob(f".{destination_path.name}.*.tmp")) == []


@pytest.mark.parametrize("sidecar_suffix", ["-wal", "-shm", "-journal"])
def test_restore_rejects_source_sidecars_without_replacement(
    sidecar_suffix: str,
    tmp_path,
) -> None:
    backup_path = tmp_path / "source.sqlite"
    backup_repository = _repository(backup_path)
    _add_invoice(backup_repository, "INV-SOURCE")
    database_path = tmp_path / "destination.sqlite"
    destination_repository = _repository(database_path)
    _add_invoice(destination_repository, "INV-KEEP")
    original_source = backup_path.read_bytes()
    original_destination = database_path.read_bytes()
    sidecar_path = Path(f"{backup_path}{sidecar_suffix}")
    sidecar_path.touch()

    with pytest.raises(ReferenceDataMaintenanceError):
        restore_database(backup_path, database_path)

    assert backup_path.read_bytes() == original_source
    assert database_path.read_bytes() == original_destination
    assert sidecar_path.exists()
    assert list(tmp_path.glob(f".{database_path.name}.*.tmp")) == []


@pytest.mark.parametrize("operation", [backup_database, restore_database])
@pytest.mark.parametrize("sidecar_suffix", ["-wal", "-shm", "-journal"])
def test_maintenance_rejects_a_source_sidecar_as_its_destination(
    operation,
    sidecar_suffix: str,
    tmp_path,
) -> None:
    source_path = tmp_path / "source.sqlite"
    source_repository = _repository(source_path)
    _add_invoice(source_repository, "INV-SOURCE")
    original_source = source_path.read_bytes()
    destination_path = Path(f"{source_path}{sidecar_suffix}")

    with pytest.raises(ReferenceDataMaintenanceError):
        operation(source_path, destination_path)

    assert source_path.read_bytes() == original_source
    assert not destination_path.exists()
    assert list(tmp_path.glob(f".{destination_path.name}.*.tmp")) == []
