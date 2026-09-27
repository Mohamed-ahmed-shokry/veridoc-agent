"""Command-line backup, restore, and evidence export for the review store."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
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
        if options.command == "cases":
            if options.case_command == "list":
                return _list_cases(options)
            if options.case_command == "get":
                return _get_case(options)
        if options.command == "sessions":
            if options.session_command == "list":
                return _list_sessions(options)
            if options.session_command == "revoke":
                return _revoke_sessions(options)
            if options.session_command == "prune":
                return _prune_sessions(options)
        if options.command == "restore":
            if not options.confirm_replace:
                print("Restore requires --confirm-replace.", file=sys.stderr)
                return 2
            destination = restore_database(options.input, options.database)
            print(f"Review-data restore completed: {destination}")
            return 0
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


def _list_cases(options: argparse.Namespace) -> int:
    """Print one bounded, optionally filtered page of review cases."""
    if options.offset < 0 or not 1 <= options.limit <= 200:
        print(
            "cases list requires --offset >= 0 and 1 <= --limit <= 200.",
            file=sys.stderr,
        )
        return 2
    try:
        repository = SQLiteReviewRepository(options.database)
        repository.initialize()
        page = repository.list_cases(
            status=options.status,
            assignee_id=options.assignee_id,
            offset=options.offset,
            limit=options.limit,
        )
    except ReviewDataUnavailableError as exc:
        print(exc.message, file=sys.stderr)
        return 1

    print(f"Total review cases: {page.total}")
    for case in page.records:
        assignee = case.assignee_id or "unassigned"
        print(
            f"[{case.status}] {case.case_id} (version={case.version}, "
            f"creator={case.creator_actor_id}, assignee={assignee}, updated={case.updated_at})"
        )
    return 0


def _get_case(options: argparse.Namespace) -> int:
    """Print detailed inspection for one review case."""
    try:
        repository = SQLiteReviewRepository(options.database)
        repository.initialize()
        detail = repository.get_case(options.case_id)
    except ReviewDataUnavailableError as exc:
        print(exc.message, file=sys.stderr)
        return 1

    if detail is None:
        print(f"Review case not found: {options.case_id}", file=sys.stderr)
        return 1

    print(f"Case ID: {detail.case_id}")
    print(f"Status: {detail.status}")
    print(f"Version: {detail.version}")
    print(f"Creator: {detail.creator_actor_id}")
    print(f"Assignee: {detail.assignee_id or 'unassigned'}")
    print(f"Created At: {detail.created_at}")
    print(f"Updated At: {detail.updated_at}")

    result = detail.snapshot.result
    print(f"Verdict: {result.verdict.status}")
    print(f"Verdict Summary: {result.verdict.summary}")
    print(f"Finding Count: {result.verdict.finding_count}")
    if result.vendor_resolution:
        vr = result.vendor_resolution
        resolved = vr.legal_name or "Unresolved"
        vendor_id = vr.resolved_vendor_id or "—"
        print(
            f"Vendor Resolution: {resolved} (ID: {vendor_id}, Confidence: {vr.confidence})"
        )

    if result.findings:
        print(f"Findings ({len(result.findings)}):")
        for finding in result.findings:
            print(
                f"  - [{finding.severity}] {finding.finding_type}: {finding.explanation}"
            )

    print(f"Events ({len(detail.events)}):")
    for event in detail.events:
        prior = event.prior_status or "—"
        assigned_part = (
            f", assigned_to={event.assigned_actor_id}"
            if event.assigned_actor_id
            else ""
        )
        reason_part = f", reason={event.reason}" if event.reason else ""
        decision_part = f", decision={event.decision}" if event.decision else ""
        print(
            f"  - [{event.occurred_at}] {event.event_type} by {event.actor_id}: "
            f"{prior} -> {event.resulting_status}{assigned_part}{decision_part}{reason_part}"
        )
    return 0


def _list_sessions(options: argparse.Namespace) -> int:
    """Print one bounded, optionally filtered page of review sessions."""
    if options.offset < 0 or not 1 <= options.limit <= 200:
        print(
            "sessions list requires --offset >= 0 and 1 <= --limit <= 200.",
            file=sys.stderr,
        )
        return 2
    try:
        repository = SQLiteReviewRepository(options.database)
        repository.initialize()
        page = repository.list_sessions(
            actor_id=options.actor_id,
            active_only=options.active_only,
            offset=options.offset,
            limit=options.limit,
        )
    except ReviewDataUnavailableError as exc:
        print(exc.message, file=sys.stderr)
        return 1

    print(f"Total review sessions: {page.total}")
    for session in page.records:
        if session.is_active:
            status_label = "ACTIVE"
        elif session.revoked_at is not None:
            status_label = "REVOKED"
        else:
            status_label = "EXPIRED"
        revoked_part = f" revoked={session.revoked_at}" if session.revoked_at else ""
        print(
            f"[{status_label}] {session.session_digest[:16]}... "
            f"actor={session.actor_id} created={session.created_at} "
            f"expires={session.expires_at}{revoked_part}"
        )
    return 0


def _revoke_sessions(options: argparse.Namespace) -> int:
    """Revoke one session by digest or all active sessions for an actor."""
    if not bool(options.digest) ^ bool(options.actor_id):
        print(
            "sessions revoke requires exactly one of --digest or --actor-id.",
            file=sys.stderr,
        )
        return 2
    try:
        repository = SQLiteReviewRepository(options.database)
        repository.initialize()
        if options.digest:
            repository.revoke_session(options.digest)
            print(f"Review session revoked: {options.digest}")
            return 0
        count = repository.revoke_actor_sessions(options.actor_id)
        print(f"Revoked {count} active session(s) for actor: {options.actor_id}")
        return 0
    except ReviewDataUnavailableError as exc:
        print(exc.message, file=sys.stderr)
        return 1


def _prune_sessions(options: argparse.Namespace) -> int:
    """Prune expired review sessions older than the specified retention threshold."""
    if options.older_than_days < 0:
        print("sessions prune requires --older-than-days >= 0.", file=sys.stderr)
        return 2
    try:
        repository = SQLiteReviewRepository(options.database)
        repository.initialize()
        before = datetime.now(UTC) - timedelta(days=options.older_than_days)
        deleted = repository.prune_sessions(before=before)
        print(f"Pruned {deleted} expired review session(s).")
        return 0
    except ReviewDataUnavailableError as exc:
        print(exc.message, file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="veridoc-review",
        description=(
            "Back up, restore, inspect cases, or manage sessions for the "
            "local review database."
        ),
    )
    parser.add_argument(
        "--database",
        default=_default_database_path(),
        help="SQLite database path (defaults to VERIDOC_REVIEW_DATABASE).",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    cases_parser = commands.add_parser(
        "cases",
        help="Inspect review cases.",
    )
    case_commands = cases_parser.add_subparsers(dest="case_command", required=True)

    list_cases = case_commands.add_parser("list", help="List review cases.")
    list_cases.add_argument(
        "--status",
        choices=["unassigned", "assigned", "escalated", "decided"],
        help="Filter cases by status.",
    )
    list_cases.add_argument(
        "--assignee-id",
        help="Filter cases by assigned actor ID.",
    )
    list_cases.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Zero-based record offset (default: 0).",
    )
    list_cases.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum cases to return (1-200, default: 50).",
    )

    get_case = case_commands.add_parser(
        "get", help="Inspect one review case in detail."
    )
    get_case.add_argument(
        "--case-id",
        required=True,
        help="Review case identifier to inspect.",
    )

    sessions_parser = commands.add_parser(
        "sessions",
        help="Inspect and manage review sessions.",
    )
    session_commands = sessions_parser.add_subparsers(
        dest="session_command", required=True
    )

    list_sessions = session_commands.add_parser("list", help="List review sessions.")
    list_sessions.add_argument(
        "--actor-id",
        help="Filter sessions by actor ID.",
    )
    list_sessions.add_argument(
        "--active-only",
        action="store_true",
        help="Show only active (unexpired, unrevoked) sessions.",
    )
    list_sessions.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Zero-based record offset (default: 0).",
    )
    list_sessions.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum sessions to return (1-200, default: 50).",
    )

    revoke_session = session_commands.add_parser(
        "revoke", help="Revoke one session by digest or all sessions for an actor."
    )
    revoke_session.add_argument(
        "--digest",
        help="Session digest to revoke.",
    )
    revoke_session.add_argument(
        "--actor-id",
        help="Actor ID whose active sessions should be revoked.",
    )

    prune_sessions = session_commands.add_parser(
        "prune", help="Prune expired review sessions."
    )
    prune_sessions.add_argument(
        "--older-than-days",
        type=int,
        default=0,
        help="Prune sessions expired at least this many days ago (default: 0).",
    )

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
