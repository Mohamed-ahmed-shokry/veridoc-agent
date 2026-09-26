"""Command-line backup, restore, vendors, and audit log for reference data."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from veridoc.administration.models import (
    MAX_ADMIN_IMPORT_BYTES,
    AdminAuditContext,
    InvoiceRecordInput,
    InvoiceRecordUpdate,
    VendorRecordInput,
    VendorRecordUpdate,
)
from veridoc.administration.protocol import ReferenceDataConflictError
from veridoc.persistence.maintenance import (
    ReferenceDataMaintenanceError,
    backup_database,
    restore_database,
)
from veridoc.persistence.protocol import ReferenceDataUnavailableError
from veridoc.persistence.sqlite import SQLiteInvoiceRepository


def main(arguments: Sequence[str] | None = None) -> int:
    """Run one explicitly selected local maintenance or vendor operation."""
    parser = _parser()
    options = parser.parse_args(arguments)
    try:
        if options.command == "backup":
            destination = backup_database(options.database, options.output)
            print(f"Reference-data backup completed: {destination}")
            return 0
        if options.command == "restore":
            if not options.confirm_replace:
                print("Restore requires --confirm-replace.", file=sys.stderr)
                return 2
            destination = restore_database(options.input, options.database)
            print(f"Reference-data restore completed: {destination}")
            return 0
        if options.command == "audit-log":
            if options.offset < 0 or not 1 <= options.limit <= 200:
                print(
                    "audit-log requires --offset >= 0 and 1 <= --limit <= 200.",
                    file=sys.stderr,
                )
                return 2
            repository = SQLiteInvoiceRepository(options.database)
            repository.initialize()
            audit_page = repository.list_admin_audit_log(
                record_type=options.record_type,
                record_id=options.record_id,
                offset=options.offset,
                limit=options.limit,
            )
            print(f"Total audit entries: {audit_page.total}")
            for audit_entry in audit_page.records:
                print(
                    f"[{audit_entry.entry_id}] {audit_entry.occurred_at} "
                    f"{audit_entry.operation} {audit_entry.record_type}:{audit_entry.record_id} "
                    f"request={audit_entry.request_id}"
                )
            return 0
        if options.command == "vendors":
            repository = SQLiteInvoiceRepository(options.database)
            repository.initialize()
            if options.vendor_command == "list":
                page = repository.list_admin_vendors(
                    status=options.status, offset=0, limit=200
                )
                print(f"Total vendors: {page.total}")
                for record in page.records:
                    v = record.vendor
                    print(
                        f"[{v.status}] {v.vendor_id}: {v.legal_name} "
                        f"({v.canonical_key}) (record_id={record.metadata.record_id})"
                    )
                return 0
            if options.vendor_command == "get":
                vendor = repository.get_vendor_by_id(options.vendor_id)
                if vendor is None:
                    print(f"Vendor not found: {options.vendor_id}", file=sys.stderr)
                    return 1
                print(f"Vendor ID: {vendor.vendor_id}")
                print(f"Legal Name: {vendor.legal_name}")
                print(f"Canonical Key: {vendor.canonical_key}")
                print(f"Status: {vendor.status}")
                if vendor.aliases:
                    print(f"Aliases: {', '.join(vendor.aliases)}")
                if vendor.bank_accounts:
                    print(f"Bank Accounts: {len(vendor.bank_accounts)}")
                    for b in vendor.bank_accounts:
                        iban_part = f" (IBAN: {b.iban})" if b.iban else ""
                        print(f"  - {b.account_number}{iban_part}")
                if vendor.tax_ids:
                    print(f"Tax IDs: {len(vendor.tax_ids)}")
                    for t in vendor.tax_ids:
                        print(f"  - {t.tax_type}: {t.tax_id}")
                return 0
            if options.vendor_command == "delete":
                deleted = repository.delete_admin_vendor(
                    options.record_id, audit=_cli_audit_context()
                )
                if not deleted:
                    print(
                        f"Vendor record not found: {options.record_id}",
                        file=sys.stderr,
                    )
                    return 1
                print(f"Vendor record deleted: {options.record_id}")
                return 0
            if options.vendor_command == "add":
                vendor_input = _load_record_input(options.input, VendorRecordInput)
                if vendor_input is None:
                    return 1
                try:
                    created = repository.create_vendor(
                        vendor_input, audit=_cli_audit_context()
                    )
                except ReferenceDataConflictError as exc:
                    print(exc.code, file=sys.stderr)
                    return 1
                print(f"Vendor record created: {created.metadata.record_id}")
                return 0
            if options.vendor_command == "update":
                vendor_update = _load_record_input(options.input, VendorRecordUpdate)
                if vendor_update is None:
                    return 1
                try:
                    updated = repository.update_admin_vendor(
                        options.record_id, vendor_update, audit=_cli_audit_context()
                    )
                except ReferenceDataConflictError as exc:
                    print(exc.code, file=sys.stderr)
                    return 1
                if updated is None:
                    print(
                        f"Vendor record not found: {options.record_id}",
                        file=sys.stderr,
                    )
                    return 1
                print(f"Vendor record updated: {options.record_id}")
                return 0
        if options.command == "invoices":
            repository = SQLiteInvoiceRepository(options.database)
            repository.initialize()
            if options.invoice_command == "add":
                invoice_input = _load_record_input(options.input, InvoiceRecordInput)
                if invoice_input is None:
                    return 1
                try:
                    created_invoice = repository.create_invoice(
                        invoice_input, audit=_cli_audit_context()
                    )
                except ReferenceDataConflictError as exc:
                    print(exc.code, file=sys.stderr)
                    return 1
                print(f"Invoice record created: {created_invoice.metadata.record_id}")
                return 0
            if options.invoice_command == "update":
                invoice_update = _load_record_input(options.input, InvoiceRecordUpdate)
                if invoice_update is None:
                    return 1
                try:
                    updated_invoice = repository.update_admin_invoice(
                        options.record_id, invoice_update, audit=_cli_audit_context()
                    )
                except ReferenceDataConflictError as exc:
                    print(exc.code, file=sys.stderr)
                    return 1
                if updated_invoice is None:
                    print(
                        f"Invoice record not found: {options.record_id}",
                        file=sys.stderr,
                    )
                    return 1
                print(f"Invoice record updated: {options.record_id}")
                return 0
            if options.invoice_command == "delete":
                deleted = repository.delete_admin_invoice(
                    options.record_id, audit=_cli_audit_context()
                )
                if not deleted:
                    print(
                        f"Invoice record not found: {options.record_id}",
                        file=sys.stderr,
                    )
                    return 1
                print(f"Invoice record deleted: {options.record_id}")
                return 0
        return 2
    except (ReferenceDataMaintenanceError, ReferenceDataUnavailableError) as exc:
        message = getattr(exc, "message", str(exc))
        print(message, file=sys.stderr)
        return 1


def _cli_audit_context() -> AdminAuditContext:
    """Build the audit identity for one operator CLI mutation."""
    return AdminAuditContext(
        request_id=uuid4().hex,
        actor="admin",
        occurred_at=datetime.now(UTC),
    )


def _load_record_input[ModelT: BaseModel](
    path: str, model: type[ModelT]
) -> ModelT | None:
    """Load and validate one record JSON file, reporting safe CLI errors."""
    try:
        with open(path, "rb") as handle:
            payload = handle.read(MAX_ADMIN_IMPORT_BYTES + 1)
    except OSError:
        print("The record input file could not be read.", file=sys.stderr)
        return None
    if len(payload) > MAX_ADMIN_IMPORT_BYTES:
        print("The record input file exceeds the size limit.", file=sys.stderr)
        return None
    try:
        return model.model_validate_json(payload)
    except (ValidationError, ValueError) as exc:
        print(f"The record input file is invalid: {exc}", file=sys.stderr)
        return None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="veridoc-reference",
        description="Back up, restore, or manage reference data and vendors.",
    )
    parser.add_argument(
        "--database",
        default=_default_database_path(),
        help="SQLite database path (defaults to VERIDOC_REFERENCE_DATABASE).",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    backup = commands.add_parser("backup", help="Create an atomic SQLite backup.")
    backup.add_argument("--output", required=True, help="Backup destination path.")

    restore = commands.add_parser(
        "restore",
        help="Replace a stopped database from a validated backup.",
    )
    restore.add_argument("--input", required=True, help="Backup source path.")
    restore.add_argument(
        "--confirm-replace",
        action="store_true",
        help="Confirm replacement of the configured database.",
    )

    vendors_parser = commands.add_parser(
        "vendors",
        help="Inspect or manage vendor master data.",
    )
    vendor_commands = vendors_parser.add_subparsers(
        dest="vendor_command", required=True
    )

    list_vendors = vendor_commands.add_parser("list", help="List registered vendors.")
    list_vendors.add_argument(
        "--status",
        choices=["active", "suspended", "inactive"],
        default=None,
        help="Filter vendors by status.",
    )

    get_vendor = vendor_commands.add_parser("get", help="Get a vendor by identifier.")
    get_vendor.add_argument(
        "--vendor-id",
        required=True,
        help="Vendor identifier (e.g. vnd_001).",
    )

    add_vendor = vendor_commands.add_parser(
        "add", help="Create a vendor from a JSON file."
    )
    add_vendor.add_argument(
        "--input",
        required=True,
        help="Path to a VendorRecordInput JSON file.",
    )

    update_vendor = vendor_commands.add_parser(
        "update", help="Replace a vendor from a JSON file."
    )
    update_vendor.add_argument(
        "--record-id",
        required=True,
        help="Administrative record ID to replace.",
    )
    update_vendor.add_argument(
        "--input",
        required=True,
        help="Path to a VendorRecordUpdate JSON file.",
    )

    delete_vendor = vendor_commands.add_parser(
        "delete", help="Delete a vendor by administrative record identifier."
    )
    delete_vendor.add_argument(
        "--record-id",
        required=True,
        help="Administrative record ID to delete.",
    )

    invoices_parser = commands.add_parser(
        "invoices",
        help="Create, replace, or delete invoice records from JSON files.",
    )
    invoice_commands = invoices_parser.add_subparsers(
        dest="invoice_command", required=True
    )

    add_invoice = invoice_commands.add_parser(
        "add", help="Create an invoice from a JSON file."
    )
    add_invoice.add_argument(
        "--input",
        required=True,
        help="Path to an InvoiceRecordInput JSON file.",
    )

    update_invoice = invoice_commands.add_parser(
        "update", help="Replace an invoice from a JSON file."
    )
    update_invoice.add_argument(
        "--record-id",
        required=True,
        help="Administrative record ID to replace.",
    )
    update_invoice.add_argument(
        "--input",
        required=True,
        help="Path to an InvoiceRecordUpdate JSON file.",
    )

    delete_invoice = invoice_commands.add_parser(
        "delete", help="Delete an invoice by administrative record identifier."
    )
    delete_invoice.add_argument(
        "--record-id",
        required=True,
        help="Administrative record ID to delete.",
    )

    audit_log = commands.add_parser(
        "audit-log",
        help="List administration audit entries in insertion order.",
    )
    audit_log.add_argument(
        "--record-type",
        choices=["invoice", "purchase_order", "vendor"],
        default=None,
        help="Filter entries by record type.",
    )
    audit_log.add_argument(
        "--record-id",
        default=None,
        help="Filter entries by server record identifier.",
    )
    audit_log.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Entries to skip (default 0).",
    )
    audit_log.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Entries to return from 1 to 200 (default 100).",
    )

    return parser


def _default_database_path() -> str:
    configured = os.environ.get(
        "VERIDOC_REFERENCE_DATABASE", "veridoc-reference.sqlite3"
    ).strip()
    return configured or "veridoc-reference.sqlite3"
