"""Operator-held quarantine storage for scanner-positive uploads.

A positive scan moves the offending bytes out of the request path into a
content-addressed quarantine directory: ``objects/<sha256>`` holds the
bytes and ``manifests/<sha256>.json`` holds the typed entry record. Release
back into processing or disposal both require an explicit operator reason
and are recorded on the manifest; nothing is ever released automatically
and disposed bytes leave a tombstone so the decision stays attributable.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

_ENTRY_ID_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MAX_FILENAME_LENGTH = 128
_MAX_CONTENT_TYPE_LENGTH = 128
_MAX_SIGNATURE_LENGTH = 256
_MAX_REASON_LENGTH = 500
_STATUS_QUARANTINED = "quarantined"
_STATUS_RELEASED = "released"
_STATUS_DISPOSED = "disposed"


class QuarantineError(RuntimeError):
    """Raised when quarantine storage cannot be read or written safely."""

    code = "quarantine_unavailable"
    message = "Quarantine storage is not available on this server."

    def __init__(self) -> None:
        super().__init__(self.message)


class QuarantineNotFoundError(RuntimeError):
    """Raised when a quarantine entry does not exist."""

    code = "quarantine_entry_not_found"
    message = "The quarantine entry was not found."

    def __init__(self) -> None:
        super().__init__(self.message)


class QuarantineConflictError(RuntimeError):
    """Raised when an already-decided entry is decided again."""

    code = "quarantine_already_decided"
    message = "The quarantine entry already has an operator decision."

    def __init__(self) -> None:
        super().__init__(self.message)


@dataclass(frozen=True, slots=True)
class QuarantineEntry:
    """One typed quarantine record with its operator decision history."""

    entry_id: str
    filename: str
    declared_content_type: str | None
    size_bytes: int
    sha256: str
    signature: str
    engine: str
    scanned_at: str
    status: str
    operator_note: str | None
    decided_at: str | None
    retention_until: str


class QuarantineStore:
    """Filesystem-backed quarantine storage for one operator directory."""

    def __init__(self, directory: str) -> None:
        candidate = Path(directory)
        if not directory or not candidate.exists() or not candidate.is_dir():
            raise QuarantineError
        self._directory = candidate
        self._objects = candidate / "objects"
        self._manifests = candidate / "manifests"
        try:
            self._objects.mkdir(exist_ok=True)
            self._manifests.mkdir(exist_ok=True)
        except OSError as exc:
            raise QuarantineError from exc

    def quarantine(
        self,
        data: bytes,
        *,
        filename: str | None,
        declared_content_type: str | None,
        signature: str,
        engine: str,
        retention_days: int = 30,
    ) -> QuarantineEntry:
        """Store scanner-positive bytes and return their typed entry."""
        digest = sha256(data).hexdigest()
        existing = self._read_entry(digest)
        if existing is not None:
            return existing
        scanned_at = _utc_now()
        entry = QuarantineEntry(
            entry_id=digest,
            filename=_bounded_filename(filename),
            declared_content_type=_bounded_content_type(declared_content_type),
            size_bytes=len(data),
            sha256=digest,
            signature=_bounded_signature(signature),
            engine=engine.strip(),
            scanned_at=scanned_at,
            status=_STATUS_QUARANTINED,
            operator_note=None,
            decided_at=None,
            retention_until=_retention_until(scanned_at, retention_days),
        )
        self._write_object(digest, data)
        self._write_manifest(entry)
        return entry

    def get(self, entry_id: str) -> QuarantineEntry:
        """Return one entry by its content digest."""
        entry = self._read_entry(_validated_entry_id(entry_id))
        if entry is None:
            raise QuarantineNotFoundError
        return entry

    def list_entries(self) -> list[QuarantineEntry]:
        """Return every entry ordered by scan time."""
        try:
            names = sorted(path.name for path in self._manifests.glob("*.json"))
        except OSError as exc:
            raise QuarantineError from exc
        entries = [self.get(name[: -len(".json")]) for name in names]
        return sorted(entries, key=lambda entry: (entry.scanned_at, entry.entry_id))

    def release(self, entry_id: str, *, reason: str) -> QuarantineEntry:
        """Record an explicit operator release with its reason."""
        return self._decide(entry_id, _STATUS_RELEASED, reason)

    def dispose(self, entry_id: str, *, reason: str) -> QuarantineEntry:
        """Delete the quarantined bytes and record the disposal decision."""
        entry = self._decide(entry_id, _STATUS_DISPOSED, reason)
        try:
            (self._objects / entry.entry_id).unlink(missing_ok=True)
        except OSError as exc:
            raise QuarantineError from exc
        return entry

    def object_path(self, entry_id: str) -> Path:
        """Return the stored-bytes path for one quarantined entry."""
        entry = self.get(entry_id)
        path = self._objects / entry.entry_id
        if entry.status != _STATUS_QUARANTINED or not path.is_file():
            raise QuarantineNotFoundError
        return path

    def _decide(self, entry_id: str, status: str, reason: str) -> QuarantineEntry:
        entry = self.get(entry_id)
        if entry.status != _STATUS_QUARANTINED:
            raise QuarantineConflictError
        decided = QuarantineEntry(
            entry_id=entry.entry_id,
            filename=entry.filename,
            declared_content_type=entry.declared_content_type,
            size_bytes=entry.size_bytes,
            sha256=entry.sha256,
            signature=entry.signature,
            engine=entry.engine,
            scanned_at=entry.scanned_at,
            status=status,
            operator_note=_bounded_reason(reason),
            decided_at=_utc_now(),
            retention_until=entry.retention_until,
        )
        self._write_manifest(decided)
        return decided

    def _read_entry(self, entry_id: str) -> QuarantineEntry | None:
        path = self._manifests / f"{entry_id}.json"
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise QuarantineError from exc
        try:
            payload = json.loads(raw)
            return _hydrate_entry(payload)
        except (ValueError, TypeError, KeyError) as exc:
            raise QuarantineError from exc

    def _write_object(self, digest: str, data: bytes) -> None:
        try:
            with tempfile.NamedTemporaryFile(
                dir=self._objects, delete=False
            ) as temporary:
                temporary.write(data)
                temporary_path = Path(temporary.name)
            os.replace(temporary_path, self._objects / digest)
            os.chmod(self._objects / digest, 0o600)
        except OSError as exc:
            raise QuarantineError from exc

    def _write_manifest(self, entry: QuarantineEntry) -> None:
        payload = {
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
        }
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._manifests,
                delete=False,
            ) as temporary:
                json.dump(payload, temporary, indent=2, sort_keys=True)
                temporary.write("\n")
                temporary_path = Path(temporary.name)
            os.replace(temporary_path, self._manifests / f"{entry.entry_id}.json")
        except OSError as exc:
            raise QuarantineError from exc


def _hydrate_entry(payload: object) -> QuarantineEntry:
    if not isinstance(payload, dict):
        raise QuarantineError
    entry_id = payload["entry_id"]
    digest = payload["sha256"]
    if not (
        isinstance(entry_id, str)
        and _ENTRY_ID_PATTERN.fullmatch(entry_id)
        and entry_id == digest
    ):
        raise QuarantineError
    status = payload["status"]
    if status not in {_STATUS_QUARANTINED, _STATUS_RELEASED, _STATUS_DISPOSED}:
        raise QuarantineError
    return QuarantineEntry(
        entry_id=entry_id,
        filename=payload["filename"],
        declared_content_type=payload["declared_content_type"],
        size_bytes=payload["size_bytes"],
        sha256=digest,
        signature=payload["signature"],
        engine=payload["engine"],
        scanned_at=payload["scanned_at"],
        status=status,
        operator_note=payload["operator_note"],
        decided_at=payload["decided_at"],
        retention_until=payload["retention_until"],
    )


def _validated_entry_id(entry_id: str) -> str:
    if not _ENTRY_ID_PATTERN.fullmatch(entry_id or ""):
        raise QuarantineNotFoundError
    return entry_id


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _retention_until(scanned_at: str, retention_days: int) -> str:
    if retention_days <= 0:
        raise QuarantineError
    scanned = datetime.fromisoformat(scanned_at)
    return (scanned + timedelta(days=retention_days)).date().isoformat()


def _bounded_filename(filename: str | None) -> str:
    cleaned = (filename or "").strip().rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if not cleaned:
        return "upload"
    return cleaned[:_MAX_FILENAME_LENGTH]


def _bounded_content_type(content_type: str | None) -> str | None:
    if content_type is None:
        return None
    cleaned = content_type.strip()
    if not cleaned:
        return None
    return cleaned[:_MAX_CONTENT_TYPE_LENGTH]


def _bounded_signature(signature: str) -> str:
    cleaned = signature.strip()
    if not cleaned:
        raise QuarantineError
    return cleaned[:_MAX_SIGNATURE_LENGTH]


def _bounded_reason(reason: str) -> str:
    cleaned = reason.strip()
    if not cleaned:
        raise QuarantineError
    return cleaned[:_MAX_REASON_LENGTH]
