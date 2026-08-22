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


def test_migrate_creates_the_review_cases_table_with_a_unique_case_id(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "review.sqlite"
    with sqlite3.connect(database_path) as connection:
        migrate(connection)

        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(review_cases)")
        }
        connection.execute(
            """
            INSERT INTO review_cases (
                case_id, status, version, creator_actor_id,
                created_at, updated_at, snapshot_schema_version,
                snapshot_digest, snapshot_json
            ) VALUES ('case-1', 'unassigned', 1, 'reviewer-1',
                      '2026-08-22T00:00:00Z', '2026-08-22T00:00:00Z', 1,
                      '{}', '{}')
            """
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO review_cases (
                    case_id, status, version, creator_actor_id,
                    created_at, updated_at, snapshot_schema_version,
                    snapshot_digest, snapshot_json
                ) VALUES ('case-1', 'unassigned', 1, 'reviewer-2',
                          '2026-08-22T00:00:00Z', '2026-08-22T00:00:00Z', 1,
                          '{}', '{}')
                """
            )

    assert {
        "case_id",
        "status",
        "version",
        "creator_actor_id",
        "assignee_id",
        "created_at",
        "updated_at",
        "snapshot_schema_version",
        "snapshot_digest",
        "snapshot_json",
        "retention_until",
        "legal_hold_reason",
    } <= columns


def _insert_case(connection: sqlite3.Connection, case_id: str = "case-1") -> int:
    cursor = connection.execute(
        """
        INSERT INTO review_cases (
            case_id, status, version, creator_actor_id,
            created_at, updated_at, snapshot_schema_version,
            snapshot_digest, snapshot_json
        ) VALUES (?, 'unassigned', 1, 'reviewer-1',
                  '2026-08-22T00:00:00Z', '2026-08-22T00:00:00Z', 1, '{}', '{}')
        """,
        (case_id,),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _insert_event(
    connection: sqlite3.Connection, case_row_id: int, case_version: int
) -> None:
    connection.execute(
        """
        INSERT INTO review_events (
            case_row_id, case_version, event_type, actor_id, occurred_at,
            request_id, resulting_status
        ) VALUES (?, ?, 'case_created', 'reviewer-1', '2026-08-22T00:00:00Z',
                  'request-1', 'unassigned')
        """,
        (case_row_id, case_version),
    )


def test_migrate_creates_review_events_with_a_unique_case_version_index(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "review.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        migrate(connection)
        case_row_id = _insert_case(connection)

        _insert_event(connection, case_row_id, 1)
        with pytest.raises(sqlite3.IntegrityError):
            _insert_event(connection, case_row_id, 1)


def test_review_events_cascade_delete_with_their_case(tmp_path: Path) -> None:
    database_path = tmp_path / "review.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        migrate(connection)
        case_row_id = _insert_case(connection)
        _insert_event(connection, case_row_id, 1)

        connection.execute("DELETE FROM review_cases WHERE id = ?", (case_row_id,))

        remaining = connection.execute(
            "SELECT COUNT(*) FROM review_events WHERE case_row_id = ?", (case_row_id,)
        ).fetchone()[0]
    assert remaining == 0


def test_migrate_requires_the_not_null_review_case_columns(tmp_path: Path) -> None:
    database_path = tmp_path / "review.sqlite"
    with sqlite3.connect(database_path) as connection:
        migrate(connection)

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO review_cases (
                    status, version, creator_actor_id, created_at, updated_at,
                    snapshot_schema_version, snapshot_digest, snapshot_json
                ) VALUES ('unassigned', 1, 'reviewer-1',
                          '2026-08-22T00:00:00Z', '2026-08-22T00:00:00Z', 1,
                          '{}', '{}')
                """
            )
