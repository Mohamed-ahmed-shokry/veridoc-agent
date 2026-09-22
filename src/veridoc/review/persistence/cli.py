"""Command-line backup, restore, and evidence export for the review store."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from veridoc.review.config import DEFAULT_REVIEW_DATABASE
from veridoc.review.evidence import (
    EvidenceBundleError,
    build_evidence_bundle,
    verify_evidence_bundle,
)
from veridoc.review.persistence.maintenance import (
    ReviewDataMaintenanceError,
    backup_database,
    restore_database,
)
from veridoc.review.persistence.sqlite import SQLiteReviewRepository
from veridoc.review.protocol import ReviewDataUnavailableError


def main(arguments: Sequence[str] | None = None) -> int:
    """Run one explicitly selected local maintenance operation."""
    parser = _parser()
    options = parser.parse_args(arguments)
    try:
        if options.command == "backup":
            destination = backup_database(options.database, options.output)
            print(f"Review-data backup completed: {destination}")
            return 0
        if options.command == "export":
            return _export_case(options)
        if options.command == "verify-bundle":
            return _verify_bundle_file(options)
        if not options.confirm_replace:
            print("Restore requires --confirm-replace.", file=sys.stderr)
            return 2
        destination = restore_database(options.input, options.database)
        print(f"Review-data restore completed: {destination}")
        return 0
    except ReviewDataMaintenanceError as exc:
        print(exc.message, file=sys.stderr)
        return 1


def _export_case(options: argparse.Namespace) -> int:
    """Write one case's digest-bound evidence bundle to a file."""
    try:
        repository = SQLiteReviewRepository(options.database)
        repository.initialize()
        detail = repository.get_case(options.case_id)
    except ReviewDataUnavailableError as exc:
        print(exc.message, file=sys.stderr)
        return 1
    if detail is None:
        print("No review case exists with the given case_id.", file=sys.stderr)
        return 1
    try:
        bundle = build_evidence_bundle(detail, exported_by=options.exported_by)
    except ValueError:
        print("The exporter identity is invalid.", file=sys.stderr)
        return 1
    try:
        Path(options.output).write_bytes(bundle.model_dump_json().encode("utf-8"))
    except OSError:
        print("The evidence bundle output could not be written.", file=sys.stderr)
        return 1
    print(f"Evidence bundle exported for case {detail.case_id}.")
    return 0


def _verify_bundle_file(options: argparse.Namespace) -> int:
    """Verify one evidence bundle file without touching any store."""
    try:
        raw = Path(options.input).read_bytes()
    except OSError:
        print("The evidence bundle input could not be read.", file=sys.stderr)
        return 1
    try:
        bundle = verify_evidence_bundle(raw)
    except EvidenceBundleError as exc:
        print(exc.message, file=sys.stderr)
        return 1
    print(
        f"Evidence bundle verified: case {bundle.case.case_id} "
        f"status {bundle.case.status} version {bundle.case.version} "
        f"events {len(bundle.case.events)} digest {bundle.bundle_digest}."
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="veridoc-review",
        description=(
            "Back up, restore, or export evidence for the stopped local "
            "review database."
        ),
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

    export = commands.add_parser(
        "export",
        help="Write one case's digest-bound evidence bundle to a file.",
    )
    export.add_argument("--case-id", required=True, help="Review case identifier.")
    export.add_argument("--output", required=True, help="Bundle destination path.")
    export.add_argument(
        "--exported-by",
        default="operator",
        help="Exporter identity recorded on the bundle.",
    )

    verify_bundle = commands.add_parser(
        "verify-bundle",
        help="Verify one evidence bundle file without touching any store.",
    )
    verify_bundle.add_argument("--input", required=True, help="Bundle source path.")
    return parser


def _default_database_path() -> str:
    configured = os.environ.get(
        "VERIDOC_REVIEW_DATABASE", DEFAULT_REVIEW_DATABASE
    ).strip()
    return configured or DEFAULT_REVIEW_DATABASE
