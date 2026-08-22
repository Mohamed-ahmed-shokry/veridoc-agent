"""Forward-only SQLite schema migrations for the dedicated review store.

This mirrors ``veridoc.persistence.migrations`` deliberately: ADR 0009
requires the review store to share no tables or migrations with the
reference-data database, so the ledger engine is duplicated rather than
reused across the two independent schemas.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime


class UnsupportedReviewSchemaVersionError(RuntimeError):
    """Raised when a review database migration ledger cannot be safely advanced."""


@dataclass(frozen=True)
class Migration:
    """One ordered collection of transactional SQLite statements."""

    version: int
    statements: tuple[str, ...]


MIGRATIONS: tuple[Migration, ...] = ()
LATEST_SCHEMA_VERSION = 0


def migrate(
    connection: sqlite3.Connection,
    *,
    validate: Callable[[sqlite3.Connection], None] | None = None,
) -> None:
    """Advance and optionally validate one review SQLite schema transactionally."""
    try:
        applied = _read_applied_versions(connection)
        if applied is not None:
            _validate_applied_versions(applied)
            if applied == {migration.version for migration in MIGRATIONS}:
                if validate is not None:
                    validate(connection)
                return

        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        applied = _read_applied_versions(connection) or set()
        _validate_applied_versions(applied)

        for migration in MIGRATIONS:
            if migration.version in applied:
                continue
            for statement in migration.statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (migration.version, _timestamp()),
            )
        if validate is not None:
            validate(connection)
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def _read_applied_versions(connection: sqlite3.Connection) -> set[int] | None:
    """Return applied versions, or ``None`` when the ledger table is absent."""
    migration_table = connection.execute(
        """
        SELECT 1 FROM sqlite_schema
        WHERE type = 'table' AND name = 'schema_migrations'
        """
    ).fetchone()
    if migration_table is None:
        return None
    return {
        int(row[0])
        for row in connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
    }


def _validate_applied_versions(applied: set[int]) -> None:
    if not applied:
        return
    latest_applied = max(applied)
    expected = set(range(1, latest_applied + 1))
    if latest_applied > LATEST_SCHEMA_VERSION or applied != expected:
        raise UnsupportedReviewSchemaVersionError(
            "The review SQLite schema migration history is unsupported."
        )


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
