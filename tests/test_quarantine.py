"""Quarantine storage tests."""

import json

import pytest

from veridoc.scanning.quarantine import (
    QuarantineConflictError,
    QuarantineEntry,
    QuarantineError,
    QuarantineNotFoundError,
    QuarantineStore,
)


def _store(tmp_path) -> QuarantineStore:
    return QuarantineStore(str(tmp_path))


def test_quarantine_store_rejects_missing_directory(tmp_path) -> None:
    """A missing quarantine directory raises the unavailable error."""
    with pytest.raises(QuarantineError):
        QuarantineStore(str(tmp_path / "missing"))


def test_quarantine_store_rejects_a_file_path(tmp_path) -> None:
    """A quarantine path pointing at a file raises the unavailable error."""
    quarantine_file = tmp_path / "quarantine"
    quarantine_file.write_bytes(b"not-a-directory")
    with pytest.raises(QuarantineError):
        QuarantineStore(str(quarantine_file))


def test_quarantine_stores_bytes_and_typed_entry(tmp_path) -> None:
    """Quarantining bytes writes the object and a typed manifest."""
    store = _store(tmp_path)

    entry = store.quarantine(
        b"malicious-bytes",
        filename="invoice.pdf",
        declared_content_type="application/pdf",
        signature="Eicar-Test-Signature",
        engine="clamav",
    )

    assert isinstance(entry, QuarantineEntry)
    assert entry.status == "quarantined"
    assert entry.size_bytes == len(b"malicious-bytes")
    assert entry.signature == "Eicar-Test-Signature"
    assert entry.engine == "clamav"
    assert entry.operator_note is None
    assert entry.decided_at is None
    object_path = tmp_path / "objects" / entry.entry_id
    assert object_path.read_bytes() == b"malicious-bytes"
    manifest = json.loads(
        (tmp_path / "manifests" / f"{entry.entry_id}.json").read_text()
    )
    assert manifest["status"] == "quarantined"


def test_quarantine_is_idempotent_for_identical_bytes(tmp_path) -> None:
    """Re-quarantining identical bytes returns the original entry."""
    store = _store(tmp_path)
    first = store.quarantine(
        b"same-bytes",
        filename="a.pdf",
        declared_content_type="application/pdf",
        signature="Sig-A",
        engine="clamav",
    )
    second = store.quarantine(
        b"same-bytes",
        filename="b.pdf",
        declared_content_type="application/pdf",
        signature="Sig-B",
        engine="clamav",
    )
    assert first == second


def test_quarantine_bounds_and_sanitizes_metadata(tmp_path) -> None:
    """Filenames are sanitized and metadata is bounded."""
    store = _store(tmp_path)
    entry = store.quarantine(
        b"bytes",
        filename="../../etc/passwd",
        declared_content_type="application/pdf",
        signature="Sig",
        engine="clamav",
    )
    assert entry.filename == "passwd"
    assert "/" not in entry.filename


def test_quarantine_falls_back_to_upload_filename(tmp_path) -> None:
    """Missing filenames fall back to a safe default."""
    store = _store(tmp_path)
    entry = store.quarantine(
        b"bytes",
        filename=None,
        declared_content_type=None,
        signature="Sig",
        engine="clamav",
    )
    assert entry.filename == "upload"
    assert entry.declared_content_type is None


def test_quarantine_rejects_empty_signature(tmp_path) -> None:
    """An empty detection signature raises the unavailable error."""
    store = _store(tmp_path)
    with pytest.raises(QuarantineError):
        store.quarantine(
            b"bytes",
            filename="invoice.pdf",
            declared_content_type="application/pdf",
            signature="   ",
            engine="clamav",
        )


def test_get_returns_the_stored_entry(tmp_path) -> None:
    """Stored entries are retrievable by their content digest."""
    store = _store(tmp_path)
    entry = store.quarantine(
        b"bytes",
        filename="invoice.pdf",
        declared_content_type="application/pdf",
        signature="Sig",
        engine="clamav",
    )
    assert store.get(entry.entry_id) == entry


def test_get_rejects_malformed_entry_ids(tmp_path) -> None:
    """Malformed entry identifiers map to the not-found error."""
    store = _store(tmp_path)
    with pytest.raises(QuarantineNotFoundError):
        store.get("not-a-digest")
    with pytest.raises(QuarantineNotFoundError):
        store.get("../objects/secret")


def test_get_rejects_unknown_entry_ids(tmp_path) -> None:
    """Well-formed but unknown identifiers map to the not-found error."""
    store = _store(tmp_path)
    with pytest.raises(QuarantineNotFoundError):
        store.get("a" * 64)


def test_get_rejects_malformed_manifests(tmp_path) -> None:
    """A corrupt manifest maps to the unavailable error, never a guess."""
    store = _store(tmp_path)
    entry = store.quarantine(
        b"bytes",
        filename="invoice.pdf",
        declared_content_type="application/pdf",
        signature="Sig",
        engine="clamav",
    )
    (tmp_path / "manifests" / f"{entry.entry_id}.json").write_text("{not-json")
    with pytest.raises(QuarantineError):
        store.get(entry.entry_id)


def test_list_entries_returns_every_entry_in_documented_order(tmp_path) -> None:
    """Listing returns every entry ordered by scan time then entry id."""
    store = _store(tmp_path)
    first = store.quarantine(
        b"first",
        filename="a.pdf",
        declared_content_type="application/pdf",
        signature="Sig",
        engine="clamav",
    )
    second = store.quarantine(
        b"second",
        filename="b.pdf",
        declared_content_type="application/pdf",
        signature="Sig",
        engine="clamav",
    )
    entries = store.list_entries()
    assert {entry.entry_id for entry in entries} == {
        first.entry_id,
        second.entry_id,
    }
    assert [(entry.scanned_at, entry.entry_id) for entry in entries] == sorted(
        (entry.scanned_at, entry.entry_id) for entry in entries
    )


def test_release_records_the_operator_reason(tmp_path) -> None:
    """Release requires a reason and records it with a decision timestamp."""
    store = _store(tmp_path)
    entry = store.quarantine(
        b"bytes",
        filename="invoice.pdf",
        declared_content_type="application/pdf",
        signature="Sig",
        engine="clamav",
    )

    released = store.release(entry.entry_id, reason="False positive, vendor confirmed")

    assert released.status == "released"
    assert released.operator_note == "False positive, vendor confirmed"
    assert released.decided_at is not None
    assert store.get(entry.entry_id).status == "released"


def test_release_rejects_empty_reasons(tmp_path) -> None:
    """Release without a reason raises the unavailable error."""
    store = _store(tmp_path)
    entry = store.quarantine(
        b"bytes",
        filename="invoice.pdf",
        declared_content_type="application/pdf",
        signature="Sig",
        engine="clamav",
    )
    with pytest.raises(QuarantineError):
        store.release(entry.entry_id, reason="   ")


def test_release_rejects_already_decided_entries(tmp_path) -> None:
    """Deciding a released entry a second time raises the conflict error."""
    store = _store(tmp_path)
    entry = store.quarantine(
        b"bytes",
        filename="invoice.pdf",
        declared_content_type="application/pdf",
        signature="Sig",
        engine="clamav",
    )
    store.release(entry.entry_id, reason="False positive")
    with pytest.raises(QuarantineConflictError):
        store.dispose(entry.entry_id, reason="changed my mind")


def test_dispose_removes_bytes_and_leaves_a_tombstone(tmp_path) -> None:
    """Disposal deletes the bytes but keeps the attributed decision."""
    store = _store(tmp_path)
    entry = store.quarantine(
        b"bytes",
        filename="invoice.pdf",
        declared_content_type="application/pdf",
        signature="Sig",
        engine="clamav",
    )

    disposed = store.dispose(entry.entry_id, reason="Confirmed malware, destroyed")

    assert disposed.status == "disposed"
    assert disposed.operator_note == "Confirmed malware, destroyed"
    assert not (tmp_path / "objects" / entry.entry_id).exists()
    assert store.get(entry.entry_id).status == "disposed"


def test_object_path_returns_stored_bytes_for_quarantined_entries(tmp_path) -> None:
    """The operator can retrieve bytes only while an entry is quarantined."""
    store = _store(tmp_path)
    entry = store.quarantine(
        b"bytes",
        filename="invoice.pdf",
        declared_content_type="application/pdf",
        signature="Sig",
        engine="clamav",
    )
    assert store.object_path(entry.entry_id).read_bytes() == b"bytes"


def test_object_path_rejects_decided_entries(tmp_path) -> None:
    """Released entries no longer expose retrievable bytes."""
    store = _store(tmp_path)
    entry = store.quarantine(
        b"bytes",
        filename="invoice.pdf",
        declared_content_type="application/pdf",
        signature="Sig",
        engine="clamav",
    )
    store.release(entry.entry_id, reason="False positive")
    with pytest.raises(QuarantineNotFoundError):
        store.object_path(entry.entry_id)
