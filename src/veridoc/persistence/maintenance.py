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
