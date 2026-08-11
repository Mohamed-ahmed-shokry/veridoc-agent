"""Safe local backup and restore operations for SQLite reference data."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from veridoc.persistence.migrations import (
    UnsupportedSchemaVersionError,
    migrate,
)
from veridoc.persistence.schema import (
    InvalidReferenceSchemaError,
    validate_current_schema,
)


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
    validation_temporary: Path | None = None
    try:
        _require_distinct_existing_source(source, destination)
        _require_no_live_sidecars(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = _temporary_sibling(destination)
        validation_temporary = _temporary_sibling(destination)
        with (
            closing(sqlite3.connect(source)) as source_connection,
            closing(sqlite3.connect(temporary)) as backup_connection,
        ):
            source_connection.backup(backup_connection)
            _validate_integrity(backup_connection)
            with closing(
                sqlite3.connect(validation_temporary)
            ) as validation_connection:
                backup_connection.backup(validation_connection)
                migrate(validation_connection, validate=validate_current_schema)
                _validate_integrity(validation_connection)
        os.replace(temporary, destination)
    except (
        OSError,
        sqlite3.Error,
        InvalidReferenceSchemaError,
        UnsupportedSchemaVersionError,
    ) as exc:
        raise ReferenceDataMaintenanceError from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if validation_temporary is not None:
            validation_temporary.unlink(missing_ok=True)
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
                migrate(restore_connection, validate=validate_current_schema)
                _validate_integrity(restore_connection)
        os.replace(temporary, destination)
    except (
        OSError,
        sqlite3.Error,
        InvalidReferenceSchemaError,
        UnsupportedSchemaVersionError,
    ) as exc:
        raise ReferenceDataMaintenanceError from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return destination


def _require_distinct_existing_source(source: Path, destination: Path) -> None:
    if source == destination or not source.is_file():
        raise ReferenceDataMaintenanceError


def _require_no_live_sidecars(database_path: Path) -> None:
    for suffix in ("-wal", "-shm", "-journal"):
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
    foreign_key_violation = connection.execute("PRAGMA foreign_key_check").fetchone()
    if result != ("ok",) or foreign_key_violation is not None:
        raise ReferenceDataMaintenanceError
