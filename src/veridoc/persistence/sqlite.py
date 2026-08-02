"""SQLite adapter for vendor invoice and purchase-order reference facts."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast

from veridoc.persistence.migrations import UnsupportedSchemaVersionError, migrate
from veridoc.persistence.protocol import ReferenceDataUnavailableError
from veridoc.verification.references import (
    HistoricalInvoice,
    PurchaseOrder,
    ReferenceLineItem,
)


class SQLiteInvoiceRepository:
    """Persist vendor reference facts in a local SQLite database."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)

    def initialize(self) -> None:
        """Migrate the reference-data database to the latest supported schema."""
        try:
            self._database_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ReferenceDataUnavailableError from exc
        with self._connection() as connection:
            migrate(connection)

    def add_invoice(self, invoice: HistoricalInvoice) -> None:
        """Persist one historical invoice and its line items."""
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO vendor_invoices (
                    vendor_key, invoice_number, purchase_order_number, invoice_date,
                    due_date, currency, subtotal, tax, discount, total, payment_terms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice.vendor_key,
                    invoice.invoice_number,
                    invoice.purchase_order_number,
                    _date_to_text(invoice.invoice_date),
                    _date_to_text(invoice.due_date),
                    invoice.currency,
                    _decimal_to_text(invoice.subtotal),
                    _decimal_to_text(invoice.tax),
                    _decimal_to_text(invoice.discount),
                    _decimal_to_text(invoice.total),
                    invoice.payment_terms,
                ),
            )
            _insert_line_items(
                connection,
                "invoice_line_items",
                "invoice_id",
                cast(int, cursor.lastrowid),
                invoice.line_items,
            )

    def add_purchase_order(self, purchase_order: PurchaseOrder) -> None:
        """Persist one purchase order and its line items."""
        with self._connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO purchase_orders (
                    vendor_key, purchase_order_number, currency, total
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    purchase_order.vendor_key,
                    purchase_order.purchase_order_number,
                    purchase_order.currency,
                    _decimal_to_text(purchase_order.total),
                ),
            )
            _insert_line_items(
                connection,
                "purchase_order_line_items",
                "purchase_order_id",
                cast(int, cursor.lastrowid),
                purchase_order.line_items,
            )

    def list_vendor_invoices(self, vendor_key: str) -> list[HistoricalInvoice]:
        """Return one vendor's invoices in insertion order."""
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM vendor_invoices WHERE vendor_key = ? ORDER BY id",
                (vendor_key,),
            ).fetchall()
            return [_invoice_from_row(connection, row) for row in rows]

    def find_invoice(
        self, vendor_key: str, invoice_number: str
    ) -> HistoricalInvoice | None:
        """Return the earliest stored invoice with this vendor-local number."""
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM vendor_invoices
                WHERE vendor_key = ? AND invoice_number = ?
                ORDER BY id
                LIMIT 1
                """,
                (vendor_key, invoice_number),
            ).fetchone()
            return _invoice_from_row(connection, row) if row is not None else None

    def get_purchase_order(
        self, vendor_key: str, purchase_order_number: str
    ) -> PurchaseOrder | None:
        """Return a stored purchase order by vendor and PO number."""
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM purchase_orders
                WHERE vendor_key = ? AND purchase_order_number = ?
                """,
                (vendor_key, purchase_order_number),
            ).fetchone()
            if row is None:
                return None
            return PurchaseOrder(
                vendor_key=row["vendor_key"],
                purchase_order_number=row["purchase_order_number"],
                currency=row["currency"],
                total=_text_to_decimal(row["total"]),
                line_items=_line_items_from_rows(
                    connection,
                    "purchase_order_line_items",
                    "purchase_order_id",
                    row["id"],
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Translate SQLite failures without leaking database details."""
        try:
            with self._connect() as connection:
                yield connection
        except (sqlite3.Error, UnsupportedSchemaVersionError) as exc:
            raise ReferenceDataUnavailableError from exc


def _insert_line_items(
    connection: sqlite3.Connection,
    table_name: str,
    parent_column: str,
    parent_id: int,
    line_items: list[ReferenceLineItem],
) -> None:
    statement = f"""
        INSERT INTO {table_name} (
            {parent_column}, position, description, product_identifier,
            quantity, unit_price, total_price
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    connection.executemany(
        statement,
        [
            (
                parent_id,
                position,
                line_item.description,
                line_item.product_identifier,
                _decimal_to_text(line_item.quantity),
                _decimal_to_text(line_item.unit_price),
                _decimal_to_text(line_item.total_price),
            )
            for position, line_item in enumerate(line_items)
        ],
    )


def _invoice_from_row(
    connection: sqlite3.Connection, row: sqlite3.Row
) -> HistoricalInvoice:
    return HistoricalInvoice(
        vendor_key=row["vendor_key"],
        invoice_number=row["invoice_number"],
        purchase_order_number=row["purchase_order_number"],
        invoice_date=_text_to_date(row["invoice_date"]),
        due_date=_text_to_date(row["due_date"]),
        currency=row["currency"],
        subtotal=_text_to_decimal(row["subtotal"]),
        tax=_text_to_decimal(row["tax"]),
        discount=_text_to_decimal(row["discount"]),
        total=_text_to_decimal(row["total"]),
        payment_terms=row["payment_terms"],
        line_items=_line_items_from_rows(
            connection, "invoice_line_items", "invoice_id", row["id"]
        ),
    )


def _line_items_from_rows(
    connection: sqlite3.Connection,
    table_name: str,
    parent_column: str,
    parent_id: int,
) -> list[ReferenceLineItem]:
    rows = connection.execute(
        f"SELECT * FROM {table_name} WHERE {parent_column} = ? ORDER BY position",
        (parent_id,),
    ).fetchall()
    return [
        ReferenceLineItem(
            description=row["description"],
            product_identifier=row["product_identifier"],
            quantity=_text_to_decimal(row["quantity"]),
            unit_price=_text_to_decimal(row["unit_price"]),
            total_price=_text_to_decimal(row["total_price"]),
        )
        for row in rows
    ]


def _decimal_to_text(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _text_to_decimal(value: str | None) -> Decimal | None:
    return Decimal(value) if value is not None else None


def _date_to_text(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _text_to_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value is not None else None
