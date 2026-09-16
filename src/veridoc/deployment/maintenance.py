"""Automated backup, retention, and quarantine maintenance for deployment.

ADR 0015 requires automated retention keeping the two most recent verified
backups per store plus the live database, with scheduled backups to an operator
backup volume. ADR 0016 requires quarantine retention and disposal controls.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from veridoc.persistence.maintenance import (
    backup_database as backup_reference_database,
)
from veridoc.review.persistence.maintenance import (
    backup_database as backup_review_database,
)
from veridoc.scanning.quarantine import QuarantineStore

_DEFAULT_REFERENCE_DATABASE = "veridoc-reference.sqlite3"
_DEFAULT_REVIEW_DATABASE = "veridoc-review.sqlite3"
_DEFAULT_BACKUP_DIR = "backups"
_DEFAULT_KEEP_COUNT = 2


def prune_backup_retention(
    backup_dir: Path,
    *,
    prefix: str,
    keep_count: int = _DEFAULT_KEEP_COUNT,
) -> list[Path]:
    """Prune older backups matching prefix, keeping the most recent keep_count."""
    if not backup_dir.is_dir():
        return []
    matching = [
        path
        for path in backup_dir.iterdir()
        if path.is_file()
        and path.name.startswith(prefix)
        and path.name.endswith(".sqlite3")
    ]
    matching.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    retained = matching[:keep_count]
    to_delete = matching[keep_count:]
    for path in to_delete:
        try:
            path.unlink()
        except OSError:
            pass
    return retained


def run_deployment_maintenance(
    *,
    reference_db: Path | str = _DEFAULT_REFERENCE_DATABASE,
    review_db: Path | str = _DEFAULT_REVIEW_DATABASE,
    backup_dir: Path | str = _DEFAULT_BACKUP_DIR,
    quarantine_dir: Path | str | None = None,
    keep_count: int = _DEFAULT_KEEP_COUNT,
    timestamp: str | None = None,
) -> dict[str, object]:
    """Execute scheduled backups and retention pruning for both stores."""
    destination_directory = Path(backup_dir)
    destination_directory.mkdir(parents=True, exist_ok=True)
    ts = timestamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    ref_dest = destination_directory / f"reference-backup-{ts}.sqlite3"
    ref_backup = backup_reference_database(reference_db, ref_dest)
    retained_ref = prune_backup_retention(
        destination_directory,
        prefix="reference-backup-",
        keep_count=keep_count,
    )

    rev_dest = destination_directory / f"review-backup-{ts}.sqlite3"
    rev_backup = backup_review_database(review_db, rev_dest)
    retained_rev = prune_backup_retention(
        destination_directory,
        prefix="review-backup-",
        keep_count=keep_count,
    )

    pruned_quarantine_count = 0
    if quarantine_dir is not None:
        q_path = Path(quarantine_dir)
        if q_path.is_dir():
            q_store = QuarantineStore(str(q_path))
            now_iso = datetime.now(UTC).isoformat()
            for entry in q_store.list_entries():
                if (
                    entry.status == "quarantined"
                    and entry.retention_until
                    and entry.retention_until < now_iso
                ):
                    q_store.dispose(entry.entry_id, reason="retention expired")
                    pruned_quarantine_count += 1

    return {
        "timestamp": ts,
        "reference_backup": str(ref_backup),
        "review_backup": str(rev_backup),
        "retained_reference_backups": [str(p) for p in retained_ref],
        "retained_review_backups": [str(p) for p in retained_rev],
        "pruned_quarantine_records": pruned_quarantine_count,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for automated deployment maintenance."""
    parser = argparse.ArgumentParser(
        description="Veridoc automated backup and retention maintenance.",
    )
    parser.add_argument(
        "--reference-db",
        default=os.environ.get(
            "VERIDOC_REFERENCE_DATABASE", _DEFAULT_REFERENCE_DATABASE
        ),
        help="Path to the reference SQLite database.",
    )
    parser.add_argument(
        "--review-db",
        default=os.environ.get("VERIDOC_REVIEW_DATABASE", _DEFAULT_REVIEW_DATABASE),
        help="Path to the review SQLite database.",
    )
    parser.add_argument(
        "--backup-dir",
        default=os.environ.get("VERIDOC_BACKUP_DIR", _DEFAULT_BACKUP_DIR),
        help="Directory to store backup snapshots.",
    )
    parser.add_argument(
        "--quarantine-dir",
        default=os.environ.get("VERIDOC_QUARANTINE_DIR"),
        help="Directory where quarantine records are stored.",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=int(os.environ.get("VERIDOC_BACKUP_KEEP", str(_DEFAULT_KEEP_COUNT))),
        help="Number of backup snapshots to retain per database.",
    )

    args = parser.parse_args(argv)
    try:
        result = run_deployment_maintenance(
            reference_db=args.reference_db,
            review_db=args.review_db,
            backup_dir=args.backup_dir,
            quarantine_dir=args.quarantine_dir,
            keep_count=args.keep,
        )
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
        return 0
    except (RuntimeError, OSError, ValueError) as exc:
        sys.stderr.write(f"Maintenance failed: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
