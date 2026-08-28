"""Structural validation tests for the dedicated review-store schema."""

import sqlite3
from pathlib import Path

import pytest

from veridoc.review.persistence.migrations import migrate
from veridoc.review.persistence.schema import (
    InvalidReviewSchemaError,
    validate_current_schema,
)


def _migrated_connection(tmp_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(tmp_path / "review.sqlite")
    connection.execute("PRAGMA foreign_keys = ON")
    migrate(connection)
    return connection


def test_validate_current_schema_accepts_a_freshly_migrated_database(
    tmp_path: Path,
) -> None:
    connection = _migrated_connection(tmp_path)
    validate_current_schema(connection)


def test_validate_current_schema_rejects_an_incomplete_ledger(tmp_path: Path) -> None:
    connection = _migrated_connection(tmp_path)
    connection.execute("DELETE FROM schema_migrations WHERE version = 4")

    with pytest.raises(InvalidReviewSchemaError):
        validate_current_schema(connection)


def test_validate_current_schema_rejects_a_missing_table(tmp_path: Path) -> None:
    connection = _migrated_connection(tmp_path)
    connection.execute("DROP TABLE review_sessions")

    with pytest.raises(InvalidReviewSchemaError):
        validate_current_schema(connection)


def test_validate_current_schema_rejects_an_extra_managed_column(
    tmp_path: Path,
) -> None:
    connection = _migrated_connection(tmp_path)
    connection.execute("ALTER TABLE review_sessions ADD COLUMN unexpected TEXT")

    with pytest.raises(InvalidReviewSchemaError):
        validate_current_schema(connection)


def test_validate_current_schema_rejects_a_wrong_column_type(tmp_path: Path) -> None:
    connection = _migrated_connection(tmp_path)
    connection.execute("DROP TABLE review_sessions")
    connection.execute(
        """
        CREATE TABLE review_sessions (
            id INTEGER PRIMARY KEY,
            session_digest INTEGER NOT NULL,
            actor_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked_at TEXT,
            UNIQUE(session_digest)
        )
        """
    )

    with pytest.raises(InvalidReviewSchemaError):
        validate_current_schema(connection)


def test_validate_current_schema_rejects_a_missing_not_null_constraint(
    tmp_path: Path,
) -> None:
    connection = _migrated_connection(tmp_path)
    connection.execute("DROP TABLE review_sessions")
    connection.execute(
        """
        CREATE TABLE review_sessions (
            id INTEGER PRIMARY KEY,
            session_digest TEXT,
            actor_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked_at TEXT,
            UNIQUE(session_digest)
        )
        """
    )

    with pytest.raises(InvalidReviewSchemaError):
        validate_current_schema(connection)


def test_validate_current_schema_rejects_a_missing_foreign_key(
    tmp_path: Path,
) -> None:
    connection = _migrated_connection(tmp_path)
    connection.execute("DROP TABLE review_events")
    connection.execute(
        """
        CREATE TABLE review_events (
            id INTEGER PRIMARY KEY,
            case_row_id INTEGER NOT NULL,
            case_version INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            request_id TEXT NOT NULL,
            idempotency_key TEXT,
            prior_status TEXT,
            resulting_status TEXT NOT NULL,
            reason TEXT,
            decision TEXT,
            assigned_actor_id TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX review_events_case_version_index
        ON review_events(case_row_id, case_version)
        """
    )

    with pytest.raises(InvalidReviewSchemaError):
        validate_current_schema(connection)


def test_validate_current_schema_rejects_a_missing_named_unique_index(
    tmp_path: Path,
) -> None:
    connection = _migrated_connection(tmp_path)
    connection.execute("DROP INDEX review_events_case_version_index")

    with pytest.raises(InvalidReviewSchemaError):
        validate_current_schema(connection)


def test_validate_current_schema_rejects_a_missing_anonymous_unique_index(
    tmp_path: Path,
) -> None:
    connection = _migrated_connection(tmp_path)
    connection.execute("DROP TABLE review_cases")
    connection.execute(
        """
        CREATE TABLE review_cases (
            id INTEGER PRIMARY KEY,
            case_id TEXT NOT NULL,
            status TEXT NOT NULL,
            version INTEGER NOT NULL,
            creator_actor_id TEXT NOT NULL,
            assignee_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            snapshot_schema_version INTEGER NOT NULL,
            snapshot_digest TEXT NOT NULL,
            snapshot_json TEXT NOT NULL,
            retention_until TEXT,
            legal_hold_reason TEXT
        )
        """
    )

    with pytest.raises(InvalidReviewSchemaError):
        validate_current_schema(connection)


def test_validate_current_schema_rejects_a_trigger_on_a_managed_table(
    tmp_path: Path,
) -> None:
    connection = _migrated_connection(tmp_path)
    connection.execute(
        """
        CREATE TRIGGER review_cases_guard
        AFTER UPDATE ON review_cases
        BEGIN SELECT 1; END
        """
    )

    with pytest.raises(InvalidReviewSchemaError):
        validate_current_schema(connection)
