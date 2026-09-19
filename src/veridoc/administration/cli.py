"""Command-line backup and restore for local reference data."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

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
                deleted = repository.delete_admin_vendor(options.record_id)
                if not deleted:
                    print(
                        f"Vendor record not found: {options.record_id}",
                        file=sys.stderr,
                    )
                    return 1
                print(f"Vendor record deleted: {options.record_id}")
                return 0
        return 2
    except (ReferenceDataMaintenanceError, ReferenceDataUnavailableError) as exc:
        message = getattr(exc, "message", str(exc))
        print(message, file=sys.stderr)
        return 1


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

    delete_vendor = vendor_commands.add_parser(
        "delete", help="Delete a vendor by administrative record identifier."
    )
    delete_vendor.add_argument(
        "--record-id",
        required=True,
        help="Administrative record ID to delete.",
    )

    return parser


def _default_database_path() -> str:
    configured = os.environ.get(
        "VERIDOC_REFERENCE_DATABASE", "veridoc-reference.sqlite3"
    ).strip()
    return configured or "veridoc-reference.sqlite3"
