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
_REQUIRED_PRIMARY_KEYS = {
    "schema_migrations": ("version",),
    "vendor_invoices": ("id",),
    "invoice_line_items": ("id",),
    "purchase_orders": ("id",),
    "purchase_order_line_items": ("id",),
}
_REQUIRED_INTEGER_COLUMNS = {
    "schema_migrations": frozenset({"version"}),
    "vendor_invoices": frozenset({"id"}),
    "invoice_line_items": frozenset({"id", "invoice_id", "position"}),
    "purchase_orders": frozenset({"id"}),
    "purchase_order_line_items": frozenset({"id", "purchase_order_id", "position"}),
}
_REQUIRED_NOT_NULL_COLUMNS = {
    "schema_migrations": frozenset({"applied_at"}),
    "vendor_invoices": frozenset({"vendor_key"}),
    "invoice_line_items": frozenset({"invoice_id", "position"}),
    "purchase_orders": frozenset({"vendor_key", "purchase_order_number"}),
    "purchase_order_line_items": frozenset({"purchase_order_id", "position"}),
}
_REQUIRED_FOREIGN_KEYS = {
    "invoice_line_items": frozenset(
        {("invoice_id", "vendor_invoices", "id", "CASCADE")}
    ),
    "purchase_order_line_items": frozenset(
        {("purchase_order_id", "purchase_orders", "id", "CASCADE")}
    ),
}
_REQUIRED_NAMED_UNIQUE_INDEXES: dict[
    str,
    dict[str, tuple[tuple[str, ...], str | None]],
] = {
    "vendor_invoices": {
        "vendor_invoices_record_id_index": (
            ("record_id",),
            "WHERE RECORD_ID IS NOT NULL",
        ),
        "vendor_invoices_source_external_id_index": (
            ("source", "external_id"),
            "WHERE SOURCE IS NOT NULL AND EXTERNAL_ID IS NOT NULL",
        ),
    },
    "purchase_orders": {
        "purchase_orders_record_id_index": (
            ("record_id",),
            "WHERE RECORD_ID IS NOT NULL",
        ),
        "purchase_orders_source_external_id_index": (
            ("source", "external_id"),
            "WHERE SOURCE IS NOT NULL AND EXTERNAL_ID IS NOT NULL",
        ),
    },
    "invoice_line_items": {
        "invoice_line_items_invoice_position_index": (
            ("invoice_id", "position"),
            None,
        ),
    },
    "purchase_order_line_items": {
        "purchase_order_line_items_purchase_order_position_index": (
            ("purchase_order_id", "position"),
            None,
        ),
    },
}


class InvalidReferenceSchemaError(RuntimeError):
    """Raised when a database does not match the supported current schema."""


def validate_current_schema(connection: sqlite3.Connection) -> None:
    """Require the complete ledger and current structural data invariants."""
    versions = [
        int(row[0])
        for row in connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
    ]
    if versions != list(range(1, LATEST_SCHEMA_VERSION + 1)):
        raise InvalidReferenceSchemaError
    for table_name, required_columns in _REQUIRED_SCHEMA_COLUMNS.items():
        table_type = connection.execute(
            "SELECT type FROM sqlite_schema WHERE name = ?",
            (table_name,),
        ).fetchone()
        column_rows = list(
            connection.execute("SELECT * FROM pragma_table_info(?)", (table_name,))
        )
        actual_columns = {str(row[1]) for row in column_rows}
        actual_column_types = {
            str(row[1]): str(row[2]).strip().upper() for row in column_rows
        }
        primary_key = tuple(
            str(row[1])
            for row in sorted(column_rows, key=lambda row: int(row[5]))
            if int(row[5]) > 0
        )
        not_null_columns = {str(row[1]) for row in column_rows if int(row[3]) == 1}
        if (
            table_type is None
            or str(table_type[0]) != "table"
            or actual_columns != required_columns
            or any(
                actual_column_types[column_name]
                != (
                    "INTEGER"
                    if column_name in _REQUIRED_INTEGER_COLUMNS[table_name]
                    else "TEXT"
                )
                for column_name in required_columns
            )
            or primary_key != _REQUIRED_PRIMARY_KEYS[table_name]
            or not _REQUIRED_NOT_NULL_COLUMNS[table_name].issubset(not_null_columns)
        ):
            raise InvalidReferenceSchemaError

    triggered_tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT tbl_name FROM sqlite_schema WHERE type = 'trigger'"
        )
    }
    if triggered_tables.intersection(_REQUIRED_SCHEMA_COLUMNS):
        raise InvalidReferenceSchemaError

    for table_name, required_foreign_keys in _REQUIRED_FOREIGN_KEYS.items():
        actual_foreign_keys = {
            (str(row[3]), str(row[2]), str(row[4]), str(row[6]).upper())
            for row in connection.execute(
                "SELECT * FROM pragma_foreign_key_list(?)",
                (table_name,),
            )
        }
        if not required_foreign_keys.issubset(actual_foreign_keys):
            raise InvalidReferenceSchemaError

    for table_name, required_indexes in _REQUIRED_NAMED_UNIQUE_INDEXES.items():
        indexes = {
            str(row[1]): (bool(row[2]), bool(row[4]))
            for row in connection.execute(
                "SELECT * FROM pragma_index_list(?)",
                (table_name,),
            )
        }
        for index_name, (index_columns, predicate) in required_indexes.items():
            expected_partial = predicate is not None
            if indexes.get(index_name) != (True, expected_partial):
                raise InvalidReferenceSchemaError
            if _index_columns(connection, index_name) != index_columns:
                raise InvalidReferenceSchemaError
            sql_row = connection.execute(
                "SELECT sql FROM sqlite_schema WHERE type = 'index' AND name = ?",
                (index_name,),
            ).fetchone()
            normalized_sql = (
                " ".join(str(sql_row[0]).upper().split()) if sql_row else ""
            )
            _, separator, actual_predicate = normalized_sql.partition(" WHERE ")
            if predicate is None and separator:
                raise InvalidReferenceSchemaError
            if predicate is not None and (
                not separator or actual_predicate != predicate.removeprefix("WHERE ")
            ):
                raise InvalidReferenceSchemaError

    purchase_order_indexes = list(
        connection.execute("SELECT * FROM pragma_index_list('purchase_orders')")
    )
    if not any(
        bool(row[2])
        and not bool(row[4])
        and _index_columns(connection, str(row[1]))
        == ("vendor_key", "purchase_order_number")
        for row in purchase_order_indexes
    ):
        raise InvalidReferenceSchemaError


def _index_columns(connection: sqlite3.Connection, index_name: str) -> tuple[str, ...]:
    return tuple(
        str(row[2])
        for row in connection.execute(
            "SELECT * FROM pragma_index_info(?)",
            (index_name,),
        )
    )
