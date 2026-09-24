"""Forward-only SQLite schema migrations for reference data."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
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

_BACKFILL_MISSING_METADATA = Migration(
    version=3,
    statements=(
        """
        UPDATE vendor_invoices
        SET record_id = COALESCE(record_id, 'legacy-invoice-' || id),
            source = COALESCE(source, 'legacy'),
            external_id = COALESCE(external_id, 'invoice-' || id),
            created_at = COALESCE(created_at, '1970-01-01T00:00:00Z'),
            updated_at = COALESCE(updated_at, '1970-01-01T00:00:00Z')
        WHERE record_id IS NULL
           OR source IS NULL
           OR external_id IS NULL
           OR created_at IS NULL
           OR updated_at IS NULL
        """,
        """
        UPDATE purchase_orders
        SET record_id = COALESCE(record_id, 'legacy-purchase-order-' || id),
            source = COALESCE(source, 'legacy'),
            external_id = COALESCE(external_id, 'purchase-order-' || id),
            created_at = COALESCE(created_at, '1970-01-01T00:00:00Z'),
            updated_at = COALESCE(updated_at, '1970-01-01T00:00:00Z')
        WHERE record_id IS NULL
           OR source IS NULL
           OR external_id IS NULL
           OR created_at IS NULL
           OR updated_at IS NULL
        """,
    ),
)

_UNIQUE_LINE_ITEM_POSITIONS = Migration(
    version=4,
    statements=(
        """
        CREATE UNIQUE INDEX invoice_line_items_invoice_position_index
        ON invoice_line_items(invoice_id, position)
        """,
        """
        CREATE UNIQUE INDEX purchase_order_line_items_purchase_order_position_index
        ON purchase_order_line_items(purchase_order_id, position)
        """,
    ),
)

_VENDOR_MASTER_DATA = Migration(
    version=5,
    statements=(
        """
        CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY,
            vendor_id TEXT NOT NULL,
            legal_name TEXT NOT NULL,
            canonical_key TEXT NOT NULL,
            status TEXT NOT NULL,
            record_id TEXT,
            source TEXT,
            external_id TEXT,
            created_at TEXT,
            updated_at TEXT,
            retention_until TEXT
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS vendors_vendor_id_index
        ON vendors(vendor_id)
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS vendors_record_id_index
        ON vendors(record_id)
        WHERE record_id IS NOT NULL
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS vendors_source_external_id_index
        ON vendors(source, external_id)
        WHERE source IS NOT NULL AND external_id IS NOT NULL
        """,
        """
        CREATE INDEX IF NOT EXISTS vendors_canonical_key_index
        ON vendors(canonical_key)
        """,
        """
        CREATE TABLE IF NOT EXISTS vendor_aliases (
            id INTEGER PRIMARY KEY,
            vendor_id INTEGER NOT NULL
                REFERENCES vendors(id) ON DELETE CASCADE,
            alias TEXT NOT NULL,
            canonical_key TEXT NOT NULL
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS vendor_aliases_vendor_alias_index
        ON vendor_aliases(vendor_id, alias)
        """,
        """
        CREATE INDEX IF NOT EXISTS vendor_aliases_canonical_key_index
        ON vendor_aliases(canonical_key)
        """,
        """
        CREATE TABLE IF NOT EXISTS vendor_bank_accounts (
            id INTEGER PRIMARY KEY,
            vendor_id INTEGER NOT NULL
                REFERENCES vendors(id) ON DELETE CASCADE,
            account_number TEXT NOT NULL,
            bank_code TEXT,
            routing_number TEXT,
            iban TEXT,
            currency TEXT,
            is_primary INTEGER NOT NULL
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS vendor_bank_accounts_vendor_account_index
        ON vendor_bank_accounts(vendor_id, account_number)
        """,
        """
        CREATE INDEX IF NOT EXISTS vendor_bank_accounts_account_number_index
        ON vendor_bank_accounts(account_number)
        """,
        """
        CREATE INDEX IF NOT EXISTS vendor_bank_accounts_iban_index
        ON vendor_bank_accounts(iban)
        """,
        """
        CREATE TABLE IF NOT EXISTS vendor_tax_ids (
            id INTEGER PRIMARY KEY,
            vendor_id INTEGER NOT NULL
                REFERENCES vendors(id) ON DELETE CASCADE,
            tax_id TEXT NOT NULL,
            tax_type TEXT NOT NULL,
            country TEXT
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS vendor_tax_ids_vendor_tax_type_index
        ON vendor_tax_ids(vendor_id, tax_type)
        """,
        """
        CREATE INDEX IF NOT EXISTS vendor_tax_ids_tax_id_index
        ON vendor_tax_ids(tax_id)
        """,
    ),
)

_ADMIN_AUDIT_LOG = Migration(
    version=6,
    statements=(
        """
        CREATE TABLE IF NOT EXISTS admin_audit_log (
            id INTEGER PRIMARY KEY,
            occurred_at TEXT NOT NULL,
            request_id TEXT NOT NULL,
            actor TEXT NOT NULL,
            operation TEXT NOT NULL,
            record_type TEXT NOT NULL,
            record_id TEXT NOT NULL,
            before_json TEXT,
            after_json TEXT
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS admin_audit_log_record_index
        ON admin_audit_log(record_type, record_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS admin_audit_log_occurred_at_index
        ON admin_audit_log(occurred_at)
        """,
    ),
)

MIGRATIONS = (
    _INITIAL_SCHEMA,
    _ADMINISTRATION_METADATA,
    _BACKFILL_MISSING_METADATA,
    _UNIQUE_LINE_ITEM_POSITIONS,
    _VENDOR_MASTER_DATA,
    _ADMIN_AUDIT_LOG,
)
LATEST_SCHEMA_VERSION = MIGRATIONS[-1].version


def migrate(
    connection: sqlite3.Connection,
    *,
    validate: Callable[[sqlite3.Connection], None] | None = None,
) -> None:
    """Advance and optionally validate one SQLite schema transactionally."""
    try:
        applied = _read_applied_versions(connection)
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
        applied = _read_applied_versions(connection)
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


def _read_applied_versions(connection: sqlite3.Connection) -> set[int]:
    migration_table = connection.execute(
        """
        SELECT 1 FROM sqlite_schema
        WHERE type = 'table' AND name = 'schema_migrations'
        """
    ).fetchone()
    if migration_table is None:
        return set()
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
        raise UnsupportedSchemaVersionError(
            "The SQLite schema migration history is unsupported."
        )


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
