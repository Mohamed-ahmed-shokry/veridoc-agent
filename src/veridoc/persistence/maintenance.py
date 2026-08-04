"""Safe local backup and restore operations for SQLite reference data."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from veridoc.persistence.migrations import (
    LATEST_SCHEMA_VERSION,
    UnsupportedSchemaVersionError,
    migrate,
)
from veridoc.persistence.protocol import ReferenceDataUnavailableError
from veridoc.persistence.sqlite import SQLiteInvoiceRepository

_REQUIRED_SCHEMA_COLUMNS = {
    "schema_migrations": frozenset({"version", "applied_at"}),
    "vendor_invoices": frozenset(
        {
            "id",
            "vendor_key",
            "invoice_number",
            "purchase_order_number",
            "invoice_date",
            "due_date",
            "currency",
            "subtotal",
            "tax",
            "discount",
            "total",
            "payment_terms",
            "record_id",
            "source",
            "external_id",
            "created_at",
            "updated_at",
            "retention_until",
        }
    ),
    "invoice_line_items": frozenset(
        {
            "id",
            "invoice_id",
            "position",
            "description",
            "product_identifier",
            "quantity",
            "unit_price",
            "total_price",
        }
    ),
    "purchase_orders": frozenset(
        {
            "id",
            "vendor_key",
            "purchase_order_number",
            "currency",
            "total",
            "record_id",
            "source",
            "external_id",
            "created_at",
            "updated_at",
            "retention_until",
        }
    ),
    "purchase_order_line_items": frozenset(
        {
            "id",
            "purchase_order_id",
            "position",
            "description",
            "product_identifier",
            "quantity",
            "unit_price",
            "total_price",
        }
    ),
}


class ReferenceDataMaintenanceError(RuntimeError):
    """Raised when backup or restore cannot complete without data risk."""

    code = "reference_data_maintenance_failed"
    message = "Reference-data maintenance could not be completed safely."

    def __init__(self) -> None:
        super().__init__(self.message)


def backup_database(
    database_path: str | Path,
    destination_path: str | Path,
) -> Path:
    """Create an integrity-checked online backup using atomic replacement."""
    source = Path(database_path).resolve()
    destination = Path(destination_path).resolve()
    temporary: Path | None = None
    try:
        _require_distinct_existing_source(source, destination)
        SQLiteInvoiceRepository(source).initialize()
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = _temporary_sibling(destination)
        with (
            closing(sqlite3.connect(source)) as source_connection,
            closing(sqlite3.connect(temporary)) as backup_connection,
        ):
            source_connection.backup(backup_connection)
            _validate_integrity(backup_connection)
            _validate_current_schema(backup_connection)
        os.replace(temporary, destination)
    except (
        OSError,
        sqlite3.Error,
        ReferenceDataUnavailableError,
        UnsupportedSchemaVersionError,
    ) as exc:
        raise ReferenceDataMaintenanceError from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return destination


def restore_database(
    backup_path: str | Path,
    database_path: str | Path,
) -> Path:
    """Validate, migrate, and atomically restore one stopped local database."""
    source = Path(backup_path).resolve()
    destination = Path(database_path).resolve()
    temporary: Path | None = None
    try:
        _require_distinct_existing_source(source, destination)
        _require_no_live_sidecars(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = _temporary_sibling(destination)
        with closing(sqlite3.connect(source)) as source_connection:
            _validate_integrity(source_connection)
            with closing(sqlite3.connect(temporary)) as restore_connection:
                source_connection.backup(restore_connection)
                migrate(restore_connection)
                _validate_integrity(restore_connection)
                _validate_current_schema(restore_connection)
        os.replace(temporary, destination)
    except (OSError, sqlite3.Error, UnsupportedSchemaVersionError) as exc:
        raise ReferenceDataMaintenanceError from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return destination


def _require_distinct_existing_source(source: Path, destination: Path) -> None:
    if source == destination or not source.is_file():
        raise ReferenceDataMaintenanceError


def _require_no_live_sidecars(database_path: Path) -> None:
    for suffix in ("-wal", "-shm"):
        if Path(f"{database_path}{suffix}").exists():
            raise ReferenceDataMaintenanceError


def _temporary_sibling(destination: Path) -> Path:
    with tempfile.NamedTemporaryFile(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
        delete=False,
    ) as handle:
        return Path(handle.name)


def _validate_integrity(connection: sqlite3.Connection) -> None:
    result = connection.execute("PRAGMA integrity_check").fetchone()
    if result != ("ok",):
        raise ReferenceDataMaintenanceError


def _validate_current_schema(connection: sqlite3.Connection) -> None:
    versions = [
        int(row[0])
        for row in connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
    ]
    if versions != list(range(1, LATEST_SCHEMA_VERSION + 1)):
        raise ReferenceDataMaintenanceError
    for table_name, required_columns in _REQUIRED_SCHEMA_COLUMNS.items():
        actual_columns = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM pragma_table_info(?)",
                (table_name,),
            )
        }
        if not required_columns.issubset(actual_columns):
            raise ReferenceDataMaintenanceError
