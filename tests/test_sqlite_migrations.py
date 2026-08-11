"""Tests for forward-only SQLite reference-data migrations."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

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


def test_migrations_index_unique_child_positions(tmp_path) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    with sqlite3.connect(database_path) as connection:
        migrate(connection)
        invoice_id = connection.execute(
            "INSERT INTO vendor_invoices (vendor_key) VALUES ('fictional-supplies')"
        ).lastrowid
        purchase_order_id = connection.execute(
            """
            INSERT INTO purchase_orders (vendor_key, purchase_order_number)
            VALUES ('fictional-supplies', 'PO-INDEXED')
            """
        ).lastrowid
        connection.execute(
            "INSERT INTO invoice_line_items (invoice_id, position) VALUES (?, 0)",
            (invoice_id,),
        )
        connection.execute(
            """
            INSERT INTO purchase_order_line_items (purchase_order_id, position)
            VALUES (?, 0)
            """,
            (purchase_order_id,),
        )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO invoice_line_items (invoice_id, position) VALUES (?, 0)",
                (invoice_id,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO purchase_order_line_items (purchase_order_id, position)
                VALUES (?, 0)
                """,
                (purchase_order_id,),
            )

        invoice_plan = connection.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT * FROM invoice_line_items
            WHERE invoice_id = ? ORDER BY position
            """,
            (invoice_id,),
        ).fetchall()
        purchase_order_plan = connection.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT * FROM purchase_order_line_items
            WHERE purchase_order_id = ? ORDER BY position
            """,
            (purchase_order_id,),
        ).fetchall()

    assert "invoice_line_items_invoice_position_index" in str(invoice_plan)
    assert "purchase_order_line_items_purchase_order_position_index" in str(
        purchase_order_plan
    )


def test_concurrent_initial_migrations_are_serialized(tmp_path) -> None:
    database_path = tmp_path / "reference-data.sqlite"
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
        connection.execute("DROP INDEX invoice_line_items_invoice_position_index")
        connection.execute(
            "DROP INDEX purchase_order_line_items_purchase_order_position_index"
        )
        connection.execute("DELETE FROM schema_migrations WHERE version >= 3")
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
