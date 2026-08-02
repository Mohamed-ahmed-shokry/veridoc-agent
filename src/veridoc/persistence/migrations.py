"""Forward-only SQLite schema migrations for reference data."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime


class UnsupportedSchemaVersionError(RuntimeError):
    """Raised when a database migration ledger cannot be safely advanced."""


@dataclass(frozen=True)
class Migration:
    """One ordered collection of transactional SQLite statements."""

    version: int
    statements: tuple[str, ...]


_INITIAL_SCHEMA = Migration(
    version=1,
    statements=(
        """
        CREATE TABLE IF NOT EXISTS vendor_invoices (
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
        """,
        """
        CREATE INDEX IF NOT EXISTS vendor_invoices_vendor_key_index
        ON vendor_invoices(vendor_key)
        """,
        """
        CREATE INDEX IF NOT EXISTS vendor_invoices_vendor_invoice_number_index
        ON vendor_invoices(vendor_key, invoice_number)
        """,
        """
        CREATE TABLE IF NOT EXISTS invoice_line_items (
            id INTEGER PRIMARY KEY,
            invoice_id INTEGER NOT NULL
                REFERENCES vendor_invoices(id) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            description TEXT,
            product_identifier TEXT,
            quantity TEXT,
            unit_price TEXT,
            total_price TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY,
            vendor_key TEXT NOT NULL,
            purchase_order_number TEXT NOT NULL,
            currency TEXT,
            total TEXT,
            UNIQUE(vendor_key, purchase_order_number)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS purchase_order_line_items (
            id INTEGER PRIMARY KEY,
            purchase_order_id INTEGER NOT NULL
                REFERENCES purchase_orders(id) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            description TEXT,
            product_identifier TEXT,
            quantity TEXT,
            unit_price TEXT,
            total_price TEXT
        )
        """,
    ),
)

_ADMINISTRATION_METADATA = Migration(
    version=2,
    statements=(
        "ALTER TABLE vendor_invoices ADD COLUMN record_id TEXT",
        "ALTER TABLE vendor_invoices ADD COLUMN source TEXT",
        "ALTER TABLE vendor_invoices ADD COLUMN external_id TEXT",
        "ALTER TABLE vendor_invoices ADD COLUMN created_at TEXT",
        "ALTER TABLE vendor_invoices ADD COLUMN updated_at TEXT",
        "ALTER TABLE vendor_invoices ADD COLUMN retention_until TEXT",
        """
        UPDATE vendor_invoices
        SET record_id = 'legacy-invoice-' || id,
            source = 'legacy',
            external_id = 'invoice-' || id,
            created_at = '1970-01-01T00:00:00Z',
            updated_at = '1970-01-01T00:00:00Z'
        WHERE record_id IS NULL
        """,
        """
        CREATE UNIQUE INDEX vendor_invoices_record_id_index
        ON vendor_invoices(record_id)
        WHERE record_id IS NOT NULL
        """,
        """
        CREATE UNIQUE INDEX vendor_invoices_source_external_id_index
        ON vendor_invoices(source, external_id)
        WHERE source IS NOT NULL AND external_id IS NOT NULL
        """,
        "ALTER TABLE purchase_orders ADD COLUMN record_id TEXT",
        "ALTER TABLE purchase_orders ADD COLUMN source TEXT",
        "ALTER TABLE purchase_orders ADD COLUMN external_id TEXT",
        "ALTER TABLE purchase_orders ADD COLUMN created_at TEXT",
        "ALTER TABLE purchase_orders ADD COLUMN updated_at TEXT",
        "ALTER TABLE purchase_orders ADD COLUMN retention_until TEXT",
        """
        UPDATE purchase_orders
        SET record_id = 'legacy-purchase-order-' || id,
            source = 'legacy',
            external_id = 'purchase-order-' || id,
            created_at = '1970-01-01T00:00:00Z',
            updated_at = '1970-01-01T00:00:00Z'
        WHERE record_id IS NULL
        """,
        """
        CREATE UNIQUE INDEX purchase_orders_record_id_index
        ON purchase_orders(record_id)
        WHERE record_id IS NOT NULL
        """,
        """
        CREATE UNIQUE INDEX purchase_orders_source_external_id_index
        ON purchase_orders(source, external_id)
        WHERE source IS NOT NULL AND external_id IS NOT NULL
        """,
    ),
)

MIGRATIONS = (_INITIAL_SCHEMA, _ADMINISTRATION_METADATA)
LATEST_SCHEMA_VERSION = MIGRATIONS[-1].version


def migrate(connection: sqlite3.Connection) -> None:
    """Advance one SQLite connection to the latest supported schema."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    connection.commit()

    applied = {
        int(row[0])
        for row in connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
    }
    _validate_applied_versions(applied)

    for migration in MIGRATIONS:
        if migration.version in applied:
            continue
        try:
            connection.execute("BEGIN IMMEDIATE")
            for statement in migration.statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (migration.version, _timestamp()),
            )
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()


def _validate_applied_versions(applied: set[int]) -> None:
    if not applied:
        return
    latest_applied = max(applied)
    expected = set(range(1, latest_applied + 1))
    if latest_applied > LATEST_SCHEMA_VERSION or applied != expected:
        raise UnsupportedSchemaVersionError(
            "The SQLite schema migration history is unsupported."
        )


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
