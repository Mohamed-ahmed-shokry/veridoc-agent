"""Tests for forward-only SQLite reference-data migrations."""

import sqlite3

import pytest

from veridoc.persistence.migrations import (
    LATEST_SCHEMA_VERSION,
    UnsupportedSchemaVersionError,
    migrate,
)


def test_migrations_create_the_latest_schema_and_are_idempotent(tmp_path) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    with sqlite3.connect(database_path) as connection:
        migrate(connection)
        migrate(connection)

        versions = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        invoice_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(vendor_invoices)")
        }

    assert versions == [(version,) for version in range(1, LATEST_SCHEMA_VERSION + 1)]
    assert {
        "record_id",
        "source",
        "external_id",
        "created_at",
        "updated_at",
        "retention_until",
    } <= invoice_columns


def test_migrations_adopt_existing_phase_3_data(tmp_path) -> None:
    database_path = tmp_path / "reference-data.sqlite"
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
            INSERT INTO vendor_invoices (vendor_key, invoice_number, total)
            VALUES ('fictional-supplies', 'INV-LEGACY', '42.00')
            """
        )
        connection.commit()

        migrate(connection)

        metadata = connection.execute(
            """
            SELECT record_id, source, external_id, created_at, updated_at
            FROM vendor_invoices
            """
        ).fetchone()

    assert metadata == (
        "legacy-invoice-1",
        "legacy",
        "invoice-1",
        "1970-01-01T00:00:00Z",
        "1970-01-01T00:00:00Z",
    )


def test_migrations_reject_an_unknown_future_schema(tmp_path) -> None:
    database_path = tmp_path / "reference-data.sqlite"
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
            (LATEST_SCHEMA_VERSION + 1, "2026-08-03T00:00:00Z"),
        )
        connection.commit()

        with pytest.raises(UnsupportedSchemaVersionError):
            migrate(connection)


def test_migrations_backfill_writes_created_after_metadata_upgrade(tmp_path) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    with sqlite3.connect(database_path) as connection:
        migrate(connection)
        connection.execute(
            "DELETE FROM schema_migrations WHERE version = ?",
            (LATEST_SCHEMA_VERSION,),
        )
        connection.execute(
            """
            INSERT INTO vendor_invoices (vendor_key, invoice_number)
            VALUES ('fictional-supplies', 'INV-BETWEEN-MIGRATIONS')
            """
        )
        connection.commit()

        migrate(connection)

        metadata = connection.execute(
            """
            SELECT record_id, source, external_id, created_at, updated_at
            FROM vendor_invoices
            WHERE invoice_number = 'INV-BETWEEN-MIGRATIONS'
            """
        ).fetchone()

    assert metadata == (
        "legacy-invoice-1",
        "legacy",
        "invoice-1",
        "1970-01-01T00:00:00Z",
        "1970-01-01T00:00:00Z",
    )
