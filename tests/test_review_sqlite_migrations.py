"""Tests for the dedicated review-store migration ledger engine."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from veridoc.review.persistence.migrations import (
    LATEST_SCHEMA_VERSION,
    UnsupportedReviewSchemaVersionError,
    migrate,
)


def test_migrate_creates_the_ledger_table_and_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "review.sqlite"
    with sqlite3.connect(database_path) as connection:
        migrate(connection)
        migrate(connection)

        versions = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()

    assert versions == [(version,) for version in range(1, LATEST_SCHEMA_VERSION + 1)]


def test_migrate_runs_a_supplied_validator_when_already_current(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "review.sqlite"
    calls = []
    with sqlite3.connect(database_path) as connection:
        migrate(connection)
        migrate(connection, validate=calls.append)

    assert calls == [connection]


def test_concurrent_initial_migrations_are_serialized(tmp_path: Path) -> None:
    database_path = tmp_path / "review.sqlite"
    ready = Barrier(5)

    def initialize() -> None:
        with sqlite3.connect(database_path, timeout=10) as connection:
            ready.wait()
            migrate(connection)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(initialize) for _ in range(4)]
        ready.wait()
        for future in futures:
            future.result()

    with sqlite3.connect(database_path) as connection:
        versions = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()

    assert versions == [(version,) for version in range(1, LATEST_SCHEMA_VERSION + 1)]


def test_migrate_rejects_an_unknown_future_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "review.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (LATEST_SCHEMA_VERSION + 1, "2026-08-22T00:00:00Z"),
        )
        connection.commit()

        with pytest.raises(UnsupportedReviewSchemaVersionError):
            migrate(connection)
