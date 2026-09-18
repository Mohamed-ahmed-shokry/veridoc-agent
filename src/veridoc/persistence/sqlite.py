"""SQLite adapter for vendor invoice and purchase-order reference facts."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal, cast
from uuid import uuid4

from veridoc.administration.models import (
    ConflictPolicy,
    ImportResult,
    InvoiceRecord,
    InvoiceRecordInput,
    InvoiceRecordPage,
    InvoiceRecordUpdate,
    InvoiceReferenceInput,
    PurchaseOrderRecord,
    PurchaseOrderRecordInput,
    PurchaseOrderRecordPage,
    PurchaseOrderRecordUpdate,
    PurchaseOrderReferenceInput,
    ReferenceDataImport,
    ReferenceRecordMetadata,
)
from veridoc.administration.protocol import ReferenceDataConflictError
from veridoc.persistence.migrations import UnsupportedSchemaVersionError, migrate
from veridoc.persistence.protocol import ReferenceDataUnavailableError
from veridoc.persistence.schema import (
    InvalidReferenceSchemaError,
    validate_current_schema,
)
from veridoc.vendors.models import (
    VendorBankAccount,
    VendorEntity,
    VendorStatus,
    VendorTaxId,
    normalize_bank_account,
    normalize_tax_id,
    normalize_vendor_name,
)
from veridoc.verification.references import (
    HistoricalInvoice,
    PurchaseOrder,
    ReferenceLineItem,
)


class InvalidPersistedReferenceDataError(RuntimeError):
    """Raised when stored rows violate the repository's semantic contract."""


def validate_persisted_reference_data(connection: sqlite3.Connection) -> None:
    """Validate every managed parent and child row on one SQLite snapshot."""
    original_row_factory = connection.row_factory
    try:
        connection.row_factory = sqlite3.Row
        invoice_rows = connection.execute(
            "SELECT * FROM vendor_invoices ORDER BY id"
        ).fetchall()
        for row in invoice_rows:
            _admin_invoice_from_row(connection, row)
        purchase_order_rows = connection.execute(
            "SELECT * FROM purchase_orders ORDER BY id"
        ).fetchall()
        for row in purchase_order_rows:
            _admin_purchase_order_from_row(connection, row)
        vendor_rows = connection.execute("SELECT * FROM vendors ORDER BY id").fetchall()
        for row in vendor_rows:
            _vendor_entity_from_row(connection, row)
    finally:
        connection.row_factory = original_row_factory


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
            migrate(connection, validate=validate_current_schema)

    def add_invoice(self, invoice: HistoricalInvoice) -> None:
        """Persist one historical invoice and its line items."""
        validated_invoice = InvoiceReferenceInput.model_validate(
            invoice.model_dump()
        ).to_domain()
        record_id = uuid4().hex
        timestamp = _timestamp()
        with self._connection() as connection:
            _insert_invoice(
                connection,
                validated_invoice,
                record_id=record_id,
                source="application",
                external_id=f"invoice-{record_id}",
                created_at=timestamp,
                updated_at=timestamp,
                retention_until=None,
            )

    def create_invoice(self, record: InvoiceRecordInput) -> InvoiceRecord:
        """Create one managed invoice with server identity and timestamps."""
        record_id = uuid4().hex
        timestamp = _timestamp()
        with self._connection() as connection:
            try:
                invoice_id = _insert_invoice(
                    connection,
                    record.invoice.to_domain(),
                    record_id=record_id,
                    source=record.metadata.source,
                    external_id=record.metadata.external_id,
                    created_at=timestamp,
                    updated_at=timestamp,
                    retention_until=record.metadata.retention_until,
                )
            except sqlite3.IntegrityError as exc:
                raise ReferenceDataConflictError from exc
            row = connection.execute(
                "SELECT * FROM vendor_invoices WHERE id = ?", (invoice_id,)
            ).fetchone()
            return _admin_invoice_from_row(connection, row)

    def list_invoices(
        self, *, vendor_key: str | None, offset: int, limit: int
    ) -> InvoiceRecordPage:
        """Return managed invoices in stable insertion order."""
        where_clause = " WHERE vendor_key = ?" if vendor_key is not None else ""
        parameters: tuple[object, ...] = (vendor_key,) if vendor_key is not None else ()
        with self._read_connection() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM vendor_invoices{where_clause}",
                    parameters,
                ).fetchone()[0]
            )
            rows = connection.execute(
                f"""
                SELECT * FROM vendor_invoices{where_clause}
                ORDER BY id
                LIMIT ? OFFSET ?
                """,
                (*parameters, limit, offset),
            ).fetchall()
            return InvoiceRecordPage(
                records=[_admin_invoice_from_row(connection, row) for row in rows],
                offset=offset,
                limit=limit,
                total=total,
            )

    def get_admin_invoice(self, record_id: str) -> InvoiceRecord | None:
        """Return one managed invoice by its server identifier."""
        with self._read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM vendor_invoices WHERE record_id = ?", (record_id,)
            ).fetchone()
            return _admin_invoice_from_row(connection, row) if row is not None else None

    def update_admin_invoice(
        self, record_id: str, update: InvoiceRecordUpdate
    ) -> InvoiceRecord | None:
        """Replace invoice facts while preserving identity and provenance."""
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT id FROM vendor_invoices WHERE record_id = ?", (record_id,)
            ).fetchone()
            if row is None:
                return None
            invoice_id = int(row["id"])
            _update_invoice(
                connection,
                invoice_id,
                update.invoice.to_domain(),
                retention_until=update.retention_until,
                updated_at=_timestamp(),
            )
            updated_row = connection.execute(
                "SELECT * FROM vendor_invoices WHERE id = ?", (invoice_id,)
            ).fetchone()
            return _admin_invoice_from_row(connection, updated_row)

    def delete_admin_invoice(self, record_id: str) -> bool:
        """Delete one managed invoice and its child line items."""
        with self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM vendor_invoices WHERE record_id = ?", (record_id,)
            )
            return cursor.rowcount > 0

    def add_purchase_order(self, purchase_order: PurchaseOrder) -> None:
        """Persist one purchase order and its line items."""
        validated_purchase_order = PurchaseOrderReferenceInput.model_validate(
            purchase_order.model_dump()
        ).to_domain()
        record_id = uuid4().hex
        timestamp = _timestamp()
        with self._connection() as connection:
            _insert_purchase_order(
                connection,
                validated_purchase_order,
                record_id=record_id,
                source="application",
                external_id=f"purchase-order-{record_id}",
                created_at=timestamp,
                updated_at=timestamp,
                retention_until=None,
            )

    def create_purchase_order(
        self, record: PurchaseOrderRecordInput
    ) -> PurchaseOrderRecord:
        """Create one managed purchase order with server metadata."""
        record_id = uuid4().hex
        timestamp = _timestamp()
        with self._connection() as connection:
            try:
                purchase_order_id = _insert_purchase_order(
                    connection,
                    record.purchase_order.to_domain(),
                    record_id=record_id,
                    source=record.metadata.source,
                    external_id=record.metadata.external_id,
                    created_at=timestamp,
                    updated_at=timestamp,
                    retention_until=record.metadata.retention_until,
                )
            except sqlite3.IntegrityError as exc:
                raise ReferenceDataConflictError from exc
            row = connection.execute(
                "SELECT * FROM purchase_orders WHERE id = ?", (purchase_order_id,)
            ).fetchone()
            return _admin_purchase_order_from_row(connection, row)

    def list_purchase_orders(
        self, *, vendor_key: str | None, offset: int, limit: int
    ) -> PurchaseOrderRecordPage:
        """Return managed purchase orders in stable insertion order."""
        where_clause = " WHERE vendor_key = ?" if vendor_key is not None else ""
        parameters: tuple[object, ...] = (vendor_key,) if vendor_key is not None else ()
        with self._read_connection() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM purchase_orders{where_clause}",
                    parameters,
                ).fetchone()[0]
            )
            rows = connection.execute(
                f"""
                SELECT * FROM purchase_orders{where_clause}
                ORDER BY id
                LIMIT ? OFFSET ?
                """,
                (*parameters, limit, offset),
            ).fetchall()
            return PurchaseOrderRecordPage(
                records=[
                    _admin_purchase_order_from_row(connection, row) for row in rows
                ],
                offset=offset,
                limit=limit,
                total=total,
            )

    def get_admin_purchase_order(self, record_id: str) -> PurchaseOrderRecord | None:
        """Return one managed purchase order by its server identifier."""
        with self._read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM purchase_orders WHERE record_id = ?", (record_id,)
            ).fetchone()
            return (
                _admin_purchase_order_from_row(connection, row)
                if row is not None
                else None
            )

    def update_admin_purchase_order(
        self, record_id: str, update: PurchaseOrderRecordUpdate
    ) -> PurchaseOrderRecord | None:
        """Replace purchase-order facts while preserving provenance."""
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT id FROM purchase_orders WHERE record_id = ?", (record_id,)
            ).fetchone()
            if row is None:
                return None
            purchase_order_id = int(row["id"])
            try:
                _update_purchase_order(
                    connection,
                    purchase_order_id,
                    update.purchase_order.to_domain(),
                    retention_until=update.retention_until,
                    updated_at=_timestamp(),
                )
            except sqlite3.IntegrityError as exc:
                raise ReferenceDataConflictError from exc
            updated_row = connection.execute(
                "SELECT * FROM purchase_orders WHERE id = ?", (purchase_order_id,)
            ).fetchone()
            return _admin_purchase_order_from_row(connection, updated_row)

    def delete_admin_purchase_order(self, record_id: str) -> bool:
        """Delete one managed purchase order and its child line items."""
        with self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM purchase_orders WHERE record_id = ?", (record_id,)
            )
            return cursor.rowcount > 0

    def import_reference_data(
        self,
        batch: ReferenceDataImport,
        *,
        conflict: ConflictPolicy,
        dry_run: bool,
    ) -> ImportResult:
        """Apply or simulate one fully validated atomic import."""
        actions: list[ImportAction] = []
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                actions.extend(
                    _import_invoice(connection, record, conflict=conflict)
                    for record in batch.invoices
                )
                actions.extend(
                    _import_purchase_order(connection, record, conflict=conflict)
                    for record in batch.purchase_orders
                )
            except Exception:
                connection.rollback()
                raise
            else:
                if dry_run:
                    connection.rollback()
                else:
                    connection.commit()
        return ImportResult(
            dry_run=dry_run,
            created=actions.count("created"),
            replaced=actions.count("replaced"),
            skipped=actions.count("skipped"),
        )

    def list_vendor_invoices(self, vendor_key: str) -> list[HistoricalInvoice]:
        """Return one vendor's invoices in insertion order."""
        with self._read_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM vendor_invoices WHERE vendor_key = ? ORDER BY id",
                (vendor_key,),
            ).fetchall()
            return [_invoice_from_row(connection, row) for row in rows]

    def find_invoice(
        self, vendor_key: str, invoice_number: str
    ) -> HistoricalInvoice | None:
        """Return the earliest stored invoice with this vendor-local number."""
        with self._read_connection() as connection:
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
        with self._read_connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM purchase_orders
                WHERE vendor_key = ? AND purchase_order_number = ?
                """,
                (vendor_key, purchase_order_number),
            ).fetchone()
            if row is None:
                return None
            return _purchase_order_from_row(connection, row)

    def get_vendor_by_id(self, vendor_id: str) -> VendorEntity | None:
        """Return one vendor by its unique vendor identifier, if any."""
        with self._read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM vendors WHERE vendor_id = ?", (vendor_id,)
            ).fetchone()
            return _vendor_entity_from_row(connection, row) if row is not None else None

    def get_vendor_by_canonical_key(self, canonical_key: str) -> VendorEntity | None:
        """Return one vendor by its canonical slugified key, if any."""
        with self._read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM vendors WHERE canonical_key = ?", (canonical_key,)
            ).fetchone()
            return _vendor_entity_from_row(connection, row) if row is not None else None

    def find_vendors_by_alias(self, alias_key: str) -> list[VendorEntity]:
        """Return vendors that have an alias matching this canonical key."""
        with self._read_connection() as connection:
            rows = connection.execute(
                """
                SELECT v.* FROM vendors v
                JOIN vendor_aliases a ON a.vendor_id = v.id
                WHERE a.canonical_key = ?
                ORDER BY v.id
                """,
                (alias_key,),
            ).fetchall()
            seen: set[str] = set()
            result: list[VendorEntity] = []
            for row in rows:
                entity = _vendor_entity_from_row(connection, row)
                if entity.vendor_id not in seen:
                    seen.add(entity.vendor_id)
                    result.append(entity)
            return result

    def find_vendors_by_tax_id(
        self, tax_id: str, tax_type: str | None = None
    ) -> list[VendorEntity]:
        """Return vendors registered with this tax identifier."""
        clean_tax = normalize_tax_id(tax_id)
        with self._read_connection() as connection:
            if tax_type is not None:
                rows = connection.execute(
                    """
                    SELECT v.* FROM vendors v
                    JOIN vendor_tax_ids t ON t.vendor_id = v.id
                    WHERE REPLACE(REPLACE(REPLACE(UPPER(t.tax_id), ' ', ''), '-', ''), '.', '') = ?
                      AND UPPER(t.tax_type) = UPPER(?)
                    ORDER BY v.id
                    """,
                    (clean_tax, tax_type),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT v.* FROM vendors v
                    JOIN vendor_tax_ids t ON t.vendor_id = v.id
                    WHERE REPLACE(REPLACE(REPLACE(UPPER(t.tax_id), ' ', ''), '-', ''), '.', '') = ?
                    ORDER BY v.id
                    """,
                    (clean_tax,),
                ).fetchall()
            seen: set[str] = set()
            result: list[VendorEntity] = []
            for row in rows:
                entity = _vendor_entity_from_row(connection, row)
                if entity.vendor_id not in seen:
                    seen.add(entity.vendor_id)
                    result.append(entity)
            return result

    def find_vendors_by_bank_account(self, account_number: str) -> list[VendorEntity]:
        """Return vendors with this account number or IBAN."""
        clean_acct = normalize_bank_account(account_number)
        with self._read_connection() as connection:
            rows = connection.execute(
                """
                SELECT v.* FROM vendors v
                JOIN vendor_bank_accounts b ON b.vendor_id = v.id
                WHERE REPLACE(REPLACE(REPLACE(UPPER(b.account_number), ' ', ''), '-', ''), '.', '') = ?
                   OR (b.iban IS NOT NULL AND REPLACE(REPLACE(REPLACE(UPPER(b.iban), ' ', ''), '-', ''), '.', '') = ?)
                ORDER BY v.id
                """,
                (clean_acct, clean_acct),
            ).fetchall()
            seen: set[str] = set()
            result: list[VendorEntity] = []
            for row in rows:
                entity = _vendor_entity_from_row(connection, row)
                if entity.vendor_id not in seen:
                    seen.add(entity.vendor_id)
                    result.append(entity)
            return result

    def list_vendors(self, *, status: VendorStatus | None = None) -> list[VendorEntity]:
        """Return all registered vendors, optionally filtered by status."""
        with self._read_connection() as connection:
            if status is not None:
                rows = connection.execute(
                    "SELECT * FROM vendors WHERE status = ? ORDER BY id",
                    (status,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM vendors ORDER BY id"
                ).fetchall()
            return [_vendor_entity_from_row(connection, row) for row in rows]

    def add_vendor(self, vendor: VendorEntity) -> None:
        """Persist one vendor entity and its child records."""
        timestamp = _timestamp()
        created_at = vendor.created_at or timestamp
        updated_at = vendor.updated_at or timestamp
        record_id = vendor.record_id or uuid4().hex
        with self._connection() as connection:
            _insert_vendor(
                connection,
                vendor,
                record_id=record_id,
                source=vendor.source or "application",
                external_id=vendor.external_id or f"vendor-{vendor.vendor_id}",
                created_at=created_at,
                updated_at=updated_at,
                retention_until=vendor.retention_until,
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
            with closing(self._connect()) as connection, connection:
                yield connection
        except (
            sqlite3.Error,
            InvalidPersistedReferenceDataError,
            InvalidReferenceSchemaError,
            UnsupportedSchemaVersionError,
        ) as exc:
            raise ReferenceDataUnavailableError from exc

    @contextmanager
    def _read_connection(self) -> Iterator[sqlite3.Connection]:
        """Hold one consistent snapshot across a compound repository read."""
        with self._connection() as connection:
            connection.execute("BEGIN")
            yield connection


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


ImportAction = Literal["created", "replaced", "skipped"]


def _import_invoice(
    connection: sqlite3.Connection,
    record: InvoiceRecordInput,
    *,
    conflict: ConflictPolicy,
) -> ImportAction:
    existing = connection.execute(
        """
        SELECT id FROM vendor_invoices
        WHERE source = ? AND external_id = ?
        """,
        (record.metadata.source, record.metadata.external_id),
    ).fetchone()
    if existing is not None:
        if conflict == "reject":
            raise ReferenceDataConflictError
        if conflict == "skip":
            return "skipped"
        _update_invoice(
            connection,
            int(existing["id"]),
            record.invoice.to_domain(),
            retention_until=record.metadata.retention_until,
            updated_at=_timestamp(),
        )
        return "replaced"

    record_id = uuid4().hex
    timestamp = _timestamp()
    try:
        _insert_invoice(
            connection,
            record.invoice.to_domain(),
            record_id=record_id,
            source=record.metadata.source,
            external_id=record.metadata.external_id,
            created_at=timestamp,
            updated_at=timestamp,
            retention_until=record.metadata.retention_until,
        )
    except sqlite3.IntegrityError as exc:
        raise ReferenceDataConflictError from exc
    return "created"


def _import_purchase_order(
    connection: sqlite3.Connection,
    record: PurchaseOrderRecordInput,
    *,
    conflict: ConflictPolicy,
) -> ImportAction:
    existing = connection.execute(
        """
        SELECT id FROM purchase_orders
        WHERE source = ? AND external_id = ?
        """,
        (record.metadata.source, record.metadata.external_id),
    ).fetchone()
    purchase_order = record.purchase_order.to_domain()
    natural_conflict = connection.execute(
        """
        SELECT id FROM purchase_orders
        WHERE vendor_key = ? AND purchase_order_number = ?
        """,
        (purchase_order.vendor_key, purchase_order.purchase_order_number),
    ).fetchone()

    if existing is not None:
        if conflict == "reject":
            raise ReferenceDataConflictError
        if conflict == "skip":
            return "skipped"
        existing_id = int(existing["id"])
        if natural_conflict is not None and int(natural_conflict["id"]) != existing_id:
            raise ReferenceDataConflictError
        try:
            _update_purchase_order(
                connection,
                existing_id,
                purchase_order,
                retention_until=record.metadata.retention_until,
                updated_at=_timestamp(),
            )
        except sqlite3.IntegrityError as exc:
            raise ReferenceDataConflictError from exc
        return "replaced"

    if natural_conflict is not None:
        if conflict == "skip":
            return "skipped"
        raise ReferenceDataConflictError

    record_id = uuid4().hex
    timestamp = _timestamp()
    try:
        _insert_purchase_order(
            connection,
            purchase_order,
            record_id=record_id,
            source=record.metadata.source,
            external_id=record.metadata.external_id,
            created_at=timestamp,
            updated_at=timestamp,
            retention_until=record.metadata.retention_until,
        )
    except sqlite3.IntegrityError as exc:
        raise ReferenceDataConflictError from exc
    return "created"


def _insert_invoice(
    connection: sqlite3.Connection,
    invoice: HistoricalInvoice,
    *,
    record_id: str,
    source: str,
    external_id: str,
    created_at: str,
    updated_at: str,
    retention_until: date | None,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO vendor_invoices (
            vendor_key, invoice_number, purchase_order_number, invoice_date,
            due_date, currency, subtotal, tax, discount, total, payment_terms,
            record_id, source, external_id, created_at, updated_at, retention_until
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            record_id,
            source,
            external_id,
            created_at,
            updated_at,
            _date_to_text(retention_until),
        ),
    )
    invoice_id = cast(int, cursor.lastrowid)
    _insert_line_items(
        connection,
        "invoice_line_items",
        "invoice_id",
        invoice_id,
        invoice.line_items,
    )
    return invoice_id


def _update_invoice(
    connection: sqlite3.Connection,
    invoice_id: int,
    invoice: HistoricalInvoice,
    *,
    retention_until: date | None,
    updated_at: str,
) -> None:
    connection.execute(
        """
        UPDATE vendor_invoices
        SET vendor_key = ?, invoice_number = ?, purchase_order_number = ?,
            invoice_date = ?, due_date = ?, currency = ?, subtotal = ?, tax = ?,
            discount = ?, total = ?, payment_terms = ?, updated_at = ?,
            retention_until = ?
        WHERE id = ?
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
            updated_at,
            _date_to_text(retention_until),
            invoice_id,
        ),
    )
    connection.execute(
        "DELETE FROM invoice_line_items WHERE invoice_id = ?", (invoice_id,)
    )
    _insert_line_items(
        connection,
        "invoice_line_items",
        "invoice_id",
        invoice_id,
        invoice.line_items,
    )


def _insert_purchase_order(
    connection: sqlite3.Connection,
    purchase_order: PurchaseOrder,
    *,
    record_id: str,
    source: str,
    external_id: str,
    created_at: str,
    updated_at: str,
    retention_until: date | None,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO purchase_orders (
            vendor_key, purchase_order_number, currency, total, record_id,
            source, external_id, created_at, updated_at, retention_until
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            purchase_order.vendor_key,
            purchase_order.purchase_order_number,
            purchase_order.currency,
            _decimal_to_text(purchase_order.total),
            record_id,
            source,
            external_id,
            created_at,
            updated_at,
            _date_to_text(retention_until),
        ),
    )
    purchase_order_id = cast(int, cursor.lastrowid)
    _insert_line_items(
        connection,
        "purchase_order_line_items",
        "purchase_order_id",
        purchase_order_id,
        purchase_order.line_items,
    )
    return purchase_order_id


def _update_purchase_order(
    connection: sqlite3.Connection,
    purchase_order_id: int,
    purchase_order: PurchaseOrder,
    *,
    retention_until: date | None,
    updated_at: str,
) -> None:
    connection.execute(
        """
        UPDATE purchase_orders
        SET vendor_key = ?, purchase_order_number = ?, currency = ?, total = ?,
            updated_at = ?, retention_until = ?
        WHERE id = ?
        """,
        (
            purchase_order.vendor_key,
            purchase_order.purchase_order_number,
            purchase_order.currency,
            _decimal_to_text(purchase_order.total),
            updated_at,
            _date_to_text(retention_until),
            purchase_order_id,
        ),
    )
    connection.execute(
        "DELETE FROM purchase_order_line_items WHERE purchase_order_id = ?",
        (purchase_order_id,),
    )
    _insert_line_items(
        connection,
        "purchase_order_line_items",
        "purchase_order_id",
        purchase_order_id,
        purchase_order.line_items,
    )


def _invoice_from_row(
    connection: sqlite3.Connection, row: sqlite3.Row
) -> HistoricalInvoice:
    try:
        invoice = HistoricalInvoice(
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
        validated = InvoiceReferenceInput.model_validate(
            invoice.model_dump()
        ).to_domain()
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InvalidPersistedReferenceDataError from exc
    if validated != invoice:
        raise InvalidPersistedReferenceDataError
    return invoice


def _admin_invoice_from_row(
    connection: sqlite3.Connection, row: sqlite3.Row
) -> InvoiceRecord:
    invoice = _invoice_from_row(connection, row)
    try:
        return InvoiceRecord(
            metadata=ReferenceRecordMetadata(
                record_id=row["record_id"],
                source=row["source"],
                external_id=row["external_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                retention_until=_text_to_date(row["retention_until"]),
            ),
            invoice=InvoiceReferenceInput.model_validate(invoice.model_dump()),
        )
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InvalidPersistedReferenceDataError from exc


def _purchase_order_from_row(
    connection: sqlite3.Connection, row: sqlite3.Row
) -> PurchaseOrder:
    try:
        purchase_order = PurchaseOrder(
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
        validated = PurchaseOrderReferenceInput.model_validate(
            purchase_order.model_dump()
        ).to_domain()
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InvalidPersistedReferenceDataError from exc
    if validated != purchase_order:
        raise InvalidPersistedReferenceDataError
    return purchase_order


def _admin_purchase_order_from_row(
    connection: sqlite3.Connection, row: sqlite3.Row
) -> PurchaseOrderRecord:
    purchase_order = _purchase_order_from_row(connection, row)
    try:
        return PurchaseOrderRecord(
            metadata=ReferenceRecordMetadata(
                record_id=row["record_id"],
                source=row["source"],
                external_id=row["external_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                retention_until=_text_to_date(row["retention_until"]),
            ),
            purchase_order=PurchaseOrderReferenceInput.model_validate(
                purchase_order.model_dump()
            ),
        )
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InvalidPersistedReferenceDataError from exc


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
    if [row["position"] for row in rows] != list(range(len(rows))):
        raise InvalidPersistedReferenceDataError
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


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _vendor_entity_from_row(
    connection: sqlite3.Connection, row: sqlite3.Row
) -> VendorEntity:
    vendor_row_id = row["id"]
    try:
        alias_rows = connection.execute(
            "SELECT alias FROM vendor_aliases WHERE vendor_id = ? ORDER BY id",
            (vendor_row_id,),
        ).fetchall()
        aliases = [str(r["alias"]) for r in alias_rows]

        bank_rows = connection.execute(
            """
            SELECT account_number, bank_code, routing_number, iban
            FROM vendor_bank_accounts WHERE vendor_id = ? ORDER BY id
            """,
            (vendor_row_id,),
        ).fetchall()
        bank_accounts = [
            VendorBankAccount(
                account_number=str(r["account_number"]),
                bank_code=str(r["bank_code"]) if r["bank_code"] is not None else None,
                routing_number=str(r["routing_number"])
                if r["routing_number"] is not None
                else None,
                iban=str(r["iban"]) if r["iban"] is not None else None,
            )
            for r in bank_rows
        ]

        tax_rows = connection.execute(
            """
            SELECT tax_id, tax_type, country
            FROM vendor_tax_ids WHERE vendor_id = ? ORDER BY id
            """,
            (vendor_row_id,),
        ).fetchall()
        tax_ids = [
            VendorTaxId(
                tax_id=str(r["tax_id"]),
                tax_type=str(r["tax_type"]),
                country_code=str(r["country"]) if r["country"] is not None else None,
            )
            for r in tax_rows
        ]

        return VendorEntity(
            vendor_id=str(row["vendor_id"]),
            legal_name=str(row["legal_name"]),
            canonical_key=str(row["canonical_key"]),
            status=cast(VendorStatus, str(row["status"])),
            aliases=aliases,
            bank_accounts=bank_accounts,
            tax_ids=tax_ids,
            record_id=str(row["record_id"]) if row["record_id"] is not None else None,
            source=str(row["source"]) if row["source"] is not None else None,
            external_id=str(row["external_id"])
            if row["external_id"] is not None
            else None,
            created_at=str(row["created_at"])
            if row["created_at"] is not None
            else None,
            updated_at=str(row["updated_at"])
            if row["updated_at"] is not None
            else None,
            retention_until=str(row["retention_until"])
            if row["retention_until"] is not None
            else None,
        )
    except Exception as exc:
        raise InvalidPersistedReferenceDataError from exc


def _insert_vendor(
    connection: sqlite3.Connection,
    vendor: VendorEntity,
    *,
    record_id: str,
    source: str,
    external_id: str,
    created_at: str,
    updated_at: str,
    retention_until: str | None,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO vendors (
            vendor_id, legal_name, canonical_key, status,
            record_id, source, external_id, created_at, updated_at, retention_until
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            vendor.vendor_id,
            vendor.legal_name,
            vendor.canonical_key,
            vendor.status,
            record_id,
            source,
            external_id,
            created_at,
            updated_at,
            retention_until,
        ),
    )
    vendor_row_id = cast(int, cursor.lastrowid)

    for alias in vendor.aliases:
        alias_key = normalize_vendor_name(alias)
        connection.execute(
            """
            INSERT INTO vendor_aliases (vendor_id, alias, canonical_key)
            VALUES (?, ?, ?)
            """,
            (vendor_row_id, alias, alias_key),
        )

    for idx, bank in enumerate(vendor.bank_accounts):
        connection.execute(
            """
            INSERT INTO vendor_bank_accounts (
                vendor_id, account_number, bank_code, routing_number, iban, is_primary
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                vendor_row_id,
                bank.account_number,
                bank.bank_code,
                bank.routing_number,
                bank.iban,
                1 if idx == 0 else 0,
            ),
        )

    for tax in vendor.tax_ids:
        connection.execute(
            """
            INSERT INTO vendor_tax_ids (
                vendor_id, tax_id, tax_type, country
            ) VALUES (?, ?, ?, ?)
            """,
            (
                vendor_row_id,
                tax.tax_id,
                tax.tax_type,
                tax.country_code,
            ),
        )

    return vendor_row_id


SQLiteVendorRepository = SQLiteInvoiceRepository
