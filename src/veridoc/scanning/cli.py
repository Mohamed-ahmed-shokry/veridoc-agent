"""Operator maintenance interface for quarantine storage."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence

from veridoc.scanning.quarantine import (
    QuarantineConflictError,
    QuarantineEntry,
    QuarantineError,
    QuarantineNotFoundError,
    QuarantineStore,
)


def main(arguments: Sequence[str] | None = None) -> int:
    """Run one explicitly selected quarantine maintenance operation."""
    parser = _parser()
    options = parser.parse_args(arguments)
    try:
        store = QuarantineStore(_quarantine_directory(options.quarantine_dir))
        if options.command == "list":
            for entry in store.list_entries():
                print(_entry_json(entry))
            return 0
        if options.command == "release":
            released = store.release(options.entry_id, reason=options.reason)
            print(_entry_json(released))
            return 0
        disposed = store.dispose(options.entry_id, reason=options.reason)
        print(_entry_json(disposed))
        return 0
    except (QuarantineError, QuarantineNotFoundError, QuarantineConflictError) as exc:
        print(exc.message, file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="veridoc-quarantine",
        description="List, release, or dispose quarantined uploads.",
    )
    parser.add_argument(
        "--quarantine-dir",
        default=None,
        help="Quarantine directory (default: VERIDOC_QUARANTINE_DIRECTORY).",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="Print every quarantine entry as JSON.")
    release = commands.add_parser(
        "release", help="Record an operator release with its reason."
    )
    release.add_argument("--entry-id", required=True, help="Quarantine entry digest.")
    release.add_argument("--reason", required=True, help="Operator release reason.")
    dispose = commands.add_parser(
        "dispose", help="Delete quarantined bytes and record the disposal."
    )
    dispose.add_argument("--entry-id", required=True, help="Quarantine entry digest.")
    dispose.add_argument("--reason", required=True, help="Operator disposal reason.")
    return parser


def _quarantine_directory(configured: str | None) -> str:
    if configured:
        return configured
    return os.environ.get("VERIDOC_QUARANTINE_DIRECTORY", "")


def _entry_json(entry: QuarantineEntry) -> str:
    return json.dumps(
        {
            "entry_id": entry.entry_id,
            "filename": entry.filename,
            "declared_content_type": entry.declared_content_type,
            "size_bytes": entry.size_bytes,
            "sha256": entry.sha256,
            "signature": entry.signature,
            "engine": entry.engine,
            "scanned_at": entry.scanned_at,
            "status": entry.status,
            "operator_note": entry.operator_note,
            "decided_at": entry.decided_at,
            "retention_until": entry.retention_until,
        },
        sort_keys=True,
    )
