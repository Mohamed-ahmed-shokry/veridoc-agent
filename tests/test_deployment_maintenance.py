"""Tests for automated deployment backup, retention, and maintenance."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest

from veridoc.deployment.maintenance import (
    main,
    prune_backup_retention,
    run_deployment_maintenance,
)
from veridoc.persistence.sqlite import SQLiteInvoiceRepository
from veridoc.review.persistence.sqlite import SQLiteReviewRepository
from veridoc.scanning.quarantine import QuarantineStore


def test_prune_backup_retention_retains_newest_backups(tmp_path: Path) -> None:
    """Retention pruning keeps exactly the keep_count most recent matching backups."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    # Create 4 backups with distinct modification times
    b1 = backup_dir / "reference-backup-20260101T000000Z.sqlite3"
    b2 = backup_dir / "reference-backup-20260102T000000Z.sqlite3"
    b3 = backup_dir / "reference-backup-20260103T000000Z.sqlite3"
    b4 = backup_dir / "reference-backup-20260104T000000Z.sqlite3"

    for i, b in enumerate((b1, b2, b3, b4)):
        b.write_bytes(b"data")
        os.utime(b, (1000 + i * 100, 1000 + i * 100))

    retained = prune_backup_retention(
        backup_dir, prefix="reference-backup-", keep_count=2
    )

    assert len(retained) == 2
    assert retained[0] == b4
    assert retained[1] == b3
    assert b4.exists()
    assert b3.exists()
    assert not b2.exists()
    assert not b1.exists()


def test_run_deployment_maintenance_backs_up_and_prunes(tmp_path: Path) -> None:
    """Full maintenance creates valid backups for both stores and prunes older ones."""
    ref_db = tmp_path / "reference.sqlite3"
    ref_repo = SQLiteInvoiceRepository(ref_db)
    ref_repo.initialize()

    rev_db = tmp_path / "review.sqlite3"
    rev_repo = SQLiteReviewRepository(rev_db)
    rev_repo.initialize()

    backup_dir = tmp_path / "backups"

    # Run 1st maintenance
    res1 = run_deployment_maintenance(
        reference_db=ref_db,
        review_db=rev_db,
        backup_dir=backup_dir,
        keep_count=2,
        timestamp="20260901T000000Z",
    )
    assert Path(str(res1["reference_backup"])).is_file()
    assert Path(str(res1["review_backup"])).is_file()

    # Run 2nd maintenance
    res2 = run_deployment_maintenance(
        reference_db=ref_db,
        review_db=rev_db,
        backup_dir=backup_dir,
        keep_count=2,
        timestamp="20260902T000000Z",
    )

    # Run 3rd maintenance (should prune 1st)
    res3 = run_deployment_maintenance(
        reference_db=ref_db,
        review_db=rev_db,
        backup_dir=backup_dir,
        keep_count=2,
        timestamp="20260903T000000Z",
    )

    assert len(res3["retained_reference_backups"]) == 2
    assert len(res3["retained_review_backups"]) == 2
    # 1st backup should no longer exist
    assert not Path(str(res1["reference_backup"])).exists()
    # 2nd and 3rd must exist
    assert Path(str(res2["reference_backup"])).exists()
    assert Path(str(res3["reference_backup"])).exists()


def test_run_deployment_maintenance_prunes_expired_quarantine(tmp_path: Path) -> None:
    """Maintenance cleans expired quarantine files when quarantine_dir is set."""
    ref_db = tmp_path / "reference.sqlite3"
    SQLiteInvoiceRepository(ref_db).initialize()
    rev_db = tmp_path / "review.sqlite3"
    SQLiteReviewRepository(rev_db).initialize()

    q_dir = tmp_path / "quarantine"
    q_dir.mkdir()
    q_store = QuarantineStore(str(q_dir))
    entry = q_store.quarantine(
        b"malware payload",
        filename="bad.png",
        declared_content_type="image/png",
        signature="EICAR.Test",
        engine="clamav",
        retention_days=1,
    )

    manifest_path = q_dir / "manifests" / f"{entry.entry_id}.json"
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_data["retention_until"] = "2020-01-01T00:00:00+00:00"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    res = run_deployment_maintenance(
        reference_db=ref_db,
        review_db=rev_db,
        backup_dir=tmp_path / "backups",
        quarantine_dir=q_dir,
    )
    assert res["pruned_quarantine_records"] == 1


def test_deployment_maintenance_cli_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI prints structured JSON result and returns exit code 0."""
    ref_db = tmp_path / "reference.sqlite3"
    SQLiteInvoiceRepository(ref_db).initialize()
    rev_db = tmp_path / "review.sqlite3"
    SQLiteReviewRepository(rev_db).initialize()
    backup_dir = tmp_path / "backups"

    captured_out = io.StringIO()
    monkeypatch.setattr("sys.stdout", captured_out)

    exit_code = main(
        [
            "--reference-db",
            str(ref_db),
            "--review-db",
            str(rev_db),
            "--backup-dir",
            str(backup_dir),
            "--keep",
            "2",
        ]
    )

    assert exit_code == 0
    payload = json.loads(captured_out.getvalue())
    assert "reference_backup" in payload
    assert "review_backup" in payload
    assert len(payload["retained_reference_backups"]) == 1
