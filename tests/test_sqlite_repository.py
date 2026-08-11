"""SQLite repository integration tests using synthetic reference facts."""

import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from veridoc.persistence.migrations import LATEST_SCHEMA_VERSION
from veridoc.persistence.protocol import ReferenceDataUnavailableError
from veridoc.persistence.sqlite import SQLiteInvoiceRepository
from veridoc.verification.references import (
    HistoricalInvoice,
    PurchaseOrder,
    ReferenceLineItem,
)


def test_sqlite_repository_round_trips_vendor_invoice_history(tmp_path) -> None:
    repository = SQLiteInvoiceRepository(tmp_path / "reference-data.sqlite")
    repository.initialize()
    invoice = HistoricalInvoice(
        vendor_key="fictional-supplies",
        invoice_number="INV-001",
        purchase_order_number="PO-001",
        invoice_date="2026-07-01",
        due_date="2026-07-31",
        currency="USD",
        subtotal="6000.00",
        tax="1200.00",
        total="7200.00",
        payment_terms="Net 30",
        line_items=[
            ReferenceLineItem(
                product_identifier="CONSULTING",
                quantity="2",
                unit_price="3000.00",
                total_price="6000.00",
            )
        ],
    )

    repository.add_invoice(invoice)

    assert repository.list_vendor_invoices("fictional-supplies") == [invoice]
    assert repository.list_vendor_invoices("other-vendor") == []


def test_sqlite_repository_finds_duplicate_invoice_and_purchase_order(tmp_path) -> None:
    repository = SQLiteInvoiceRepository(tmp_path / "reference-data.sqlite")
    repository.initialize()
    invoice = HistoricalInvoice(
        vendor_key="fictional-supplies", invoice_number="INV-001"
    )
    purchase_order = PurchaseOrder(
        vendor_key="fictional-supplies",
        purchase_order_number="PO-001",
        currency="USD",
        total=Decimal("7200.00"),
    )
    repository.add_invoice(invoice)
    repository.add_purchase_order(purchase_order)

    assert repository.find_invoice("fictional-supplies", "INV-001") == invoice
    assert repository.find_invoice("fictional-supplies", "INV-404") is None
    assert (
        repository.get_purchase_order("fictional-supplies", "PO-001") == purchase_order
    )
    assert repository.get_purchase_order("fictional-supplies", "PO-404") is None


def test_sqlite_repository_maps_sqlite_errors_to_a_safe_boundary_error(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = SQLiteInvoiceRepository(tmp_path / "reference-data.sqlite")

    def fail_to_connect() -> sqlite3.Connection:
        raise sqlite3.OperationalError("database is unavailable")

    monkeypatch.setattr(repository, "_connect", fail_to_connect)

    with pytest.raises(ReferenceDataUnavailableError):
        repository.list_vendor_invoices("fictional-supplies")


def test_repository_maps_storage_initialization_errors_to_a_safe_boundary_error(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = SQLiteInvoiceRepository(tmp_path / "reference-data.sqlite")

    def fail_to_create_directory(
        self: Path, *, parents: bool = False, exist_ok: bool = False
    ) -> None:
        del self, parents, exist_ok
        raise OSError("storage is unavailable")

    monkeypatch.setattr(Path, "mkdir", fail_to_create_directory)

    with pytest.raises(ReferenceDataUnavailableError):
        repository.initialize()


def test_repository_maps_unsupported_schema_versions_to_a_safe_boundary_error(
    tmp_path,
) -> None:
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

    repository = SQLiteInvoiceRepository(database_path)

    with pytest.raises(ReferenceDataUnavailableError):
        repository.initialize()


def test_repository_rejects_a_missing_provenance_uniqueness_constraint(
    tmp_path,
) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    repository = SQLiteInvoiceRepository(database_path)
    repository.initialize()
    with sqlite3.connect(database_path) as connection:
        connection.execute("DROP INDEX vendor_invoices_source_external_id_index")

    with pytest.raises(ReferenceDataUnavailableError):
        repository.initialize()


def test_rejected_initialization_leaves_a_legacy_schema_unchanged(tmp_path) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE vendor_invoices (
                id INTEGER PRIMARY KEY,
                vendor_key TEXT,
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
        original_schema = connection.execute(
            """
            SELECT type, name, tbl_name, sql
            FROM sqlite_schema
            ORDER BY type, name
            """
        ).fetchall()
        original_rows = connection.execute(
            "SELECT * FROM vendor_invoices ORDER BY id"
        ).fetchall()

    repository = SQLiteInvoiceRepository(database_path)

    with pytest.raises(ReferenceDataUnavailableError):
        repository.initialize()

    with sqlite3.connect(database_path) as connection:
        final_schema = connection.execute(
            """
            SELECT type, name, tbl_name, sql
            FROM sqlite_schema
            ORDER BY type, name
            """
        ).fetchall()
        final_rows = connection.execute(
            "SELECT * FROM vendor_invoices ORDER BY id"
        ).fetchall()

    assert final_schema == original_schema
    assert final_rows == original_rows


def test_repository_rejects_a_legacy_schema_with_wrong_column_affinity(
    tmp_path,
) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE vendor_invoices (
                id TEXT PRIMARY KEY,
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

    repository = SQLiteInvoiceRepository(database_path)

    with pytest.raises(ReferenceDataUnavailableError):
        repository.initialize()


def test_repository_closes_connections_after_each_operation(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = SQLiteInvoiceRepository(tmp_path / "reference-data.sqlite")

    class ConnectionSpy:
        closed = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            del exc_type, exc_value, traceback

        def close(self) -> None:
            self.closed = True

    connection = ConnectionSpy()
    monkeypatch.setattr(repository, "_connect", lambda: connection)

    with repository._connection():
        pass

    assert connection.closed is True
