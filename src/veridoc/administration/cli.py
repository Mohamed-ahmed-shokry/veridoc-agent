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


def main(arguments: Sequence[str] | None = None) -> int:
    """Run one explicitly selected local maintenance operation."""
    parser = _parser()
    options = parser.parse_args(arguments)
    try:
        if options.command == "backup":
            destination = backup_database(options.database, options.output)
            print(f"Reference-data backup completed: {destination}")
            return 0
        if not options.confirm_replace:
            print("Restore requires --confirm-replace.", file=sys.stderr)
            return 2
        destination = restore_database(options.input, options.database)
        print(f"Reference-data restore completed: {destination}")
        return 0
    except ReferenceDataMaintenanceError as exc:
        print(exc.message, file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="veridoc-reference",
        description="Back up or restore the stopped local reference-data database.",
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
    return parser


def _default_database_path() -> str:
    configured = os.environ.get(
        "VERIDOC_REFERENCE_DATABASE", "veridoc-reference.sqlite3"
    ).strip()
    return configured or "veridoc-reference.sqlite3"
