"""Command-line backup and restore for the dedicated review store."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

from veridoc.review.config import DEFAULT_REVIEW_DATABASE
from veridoc.review.persistence.maintenance import (
    ReviewDataMaintenanceError,
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
            print(f"Review-data backup completed: {destination}")
            return 0
        if not options.confirm_replace:
            print("Restore requires --confirm-replace.", file=sys.stderr)
            return 2
        destination = restore_database(options.input, options.database)
        print(f"Review-data restore completed: {destination}")
        return 0
    except ReviewDataMaintenanceError as exc:
        print(exc.message, file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="veridoc-review",
        description="Back up or restore the stopped local review database.",
    )
    parser.add_argument(
        "--database",
        default=_default_database_path(),
        help="SQLite database path (defaults to VERIDOC_REVIEW_DATABASE).",
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
        "VERIDOC_REVIEW_DATABASE", DEFAULT_REVIEW_DATABASE
    ).strip()
    return configured or DEFAULT_REVIEW_DATABASE
