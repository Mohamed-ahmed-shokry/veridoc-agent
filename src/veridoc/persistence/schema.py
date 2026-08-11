"""Structural validation for the current SQLite reference-data schema."""

from __future__ import annotations

import sqlite3

from veridoc.persistence.migrations import LATEST_SCHEMA_VERSION

_REQUIRED_SCHEMA_COLUMNS = {
    "schema_migrations": frozenset({"version", "applied_at"}),
    "vendor_invoices": frozenset(
        {
            "id",
            "vendor_key",
            "invoice_number",
            "purchase_order_number",
            "invoice_date",
            "due_date",
            "currency",
            "subtotal",
            "tax",
            "discount",
            "total",
            "payment_terms",
            "record_id",
            "source",
            "external_id",
            "created_at",
            "updated_at",
            "retention_until",
        }
    ),
    "invoice_line_items": frozenset(
        {
            "id",
            "invoice_id",
            "position",
            "description",
            "product_identifier",
            "quantity",
            "unit_price",
            "total_price",
        }
    ),
    "purchase_orders": frozenset(
        {
            "id",
            "vendor_key",
            "purchase_order_number",
            "currency",
            "total",
            "record_id",
            "source",
            "external_id",
            "created_at",
            "updated_at",
            "retention_until",
        }
    ),
    "purchase_order_line_items": frozenset(
        {
            "id",
            "purchase_order_id",
            "position",
            "description",
            "product_identifier",
            "quantity",
            "unit_price",
            "total_price",
        }
    ),
}


class InvalidReferenceSchemaError(RuntimeError):
    """Raised when a database does not match the supported current schema."""


def validate_current_schema(connection: sqlite3.Connection) -> None:
    """Require the complete migration ledger and all current schema columns."""
    versions = [
        int(row[0])
        for row in connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
    ]
    if versions != list(range(1, LATEST_SCHEMA_VERSION + 1)):
        raise InvalidReferenceSchemaError
    for table_name, required_columns in _REQUIRED_SCHEMA_COLUMNS.items():
        actual_columns = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM pragma_table_info(?)",
                (table_name,),
            )
        }
        if not required_columns.issubset(actual_columns):
            raise InvalidReferenceSchemaError
