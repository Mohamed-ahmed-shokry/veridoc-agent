"""Tests for the quarantine maintenance command."""

import json

from veridoc.scanning.cli import main
from veridoc.scanning.quarantine import QuarantineStore


def _quarantined_entry_id(tmp_path) -> str:
    store = QuarantineStore(str(tmp_path))
    entry = store.quarantine(
        b"malicious-bytes",
        filename="invoice.pdf",
        declared_content_type="application/pdf",
        signature="Eicar-Test-Signature",
        engine="clamav",
    )
    return entry.entry_id


def test_quarantine_cli_lists_entries_as_json(tmp_path, capsys) -> None:
    """The list command prints one JSON entry per quarantined upload."""
    entry_id = _quarantined_entry_id(tmp_path)

    status = main(["--quarantine-dir", str(tmp_path), "list"])

    assert status == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["entry_id"] == entry_id
    assert payload["status"] == "quarantined"
    assert payload["signature"] == "Eicar-Test-Signature"


def test_quarantine_cli_release_records_the_reason(tmp_path, capsys) -> None:
    """The release command records the operator reason on the manifest."""
    entry_id = _quarantined_entry_id(tmp_path)

    status = main(
        [
            "--quarantine-dir",
            str(tmp_path),
            "release",
            "--entry-id",
            entry_id,
            "--reason",
            "False positive, vendor confirmed",
        ]
    )

    assert status == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "released"
    assert payload["operator_note"] == "False positive, vendor confirmed"
    assert QuarantineStore(str(tmp_path)).get(entry_id).status == "released"


def test_quarantine_cli_dispose_removes_bytes(tmp_path, capsys) -> None:
    """The dispose command deletes bytes and keeps the attributed tombstone."""
    entry_id = _quarantined_entry_id(tmp_path)

    status = main(
        [
            "--quarantine-dir",
            str(tmp_path),
            "dispose",
            "--entry-id",
            entry_id,
            "--reason",
            "Confirmed malware, destroyed",
        ]
    )

    assert status == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["status"] == "disposed"
    assert not (tmp_path / "objects" / entry_id).exists()


def test_quarantine_cli_reports_unknown_entries(tmp_path, capsys) -> None:
    """Unknown entry identifiers exit nonzero with the safe message."""
    status = main(
        [
            "--quarantine-dir",
            str(tmp_path),
            "release",
            "--entry-id",
            "a" * 64,
            "--reason",
            "operator reason",
        ]
    )

    assert status == 1
    assert "not found" in capsys.readouterr().err


def test_quarantine_cli_reports_missing_directory(tmp_path, capsys) -> None:
    """A missing quarantine directory exits nonzero with the safe message."""
    status = main(["--quarantine-dir", str(tmp_path / "missing"), "list"])

    assert status == 1
    assert "not available" in capsys.readouterr().err


def test_quarantine_cli_reads_directory_from_environment(
    tmp_path, capsys, monkeypatch
) -> None:
    """The quarantine directory falls back to its environment variable."""
    entry_id = _quarantined_entry_id(tmp_path)
    monkeypatch.setenv("VERIDOC_QUARANTINE_DIRECTORY", str(tmp_path))

    status = main(["list"])

    assert status == 0
    assert entry_id in capsys.readouterr().out
