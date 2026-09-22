"""Tests for the review evidence-bundle maintenance commands."""

import json
from pathlib import Path

import pytest

from veridoc.extraction.models import InvoiceExtraction
from veridoc.processing.models import ProcessingResult, ProcessingVerdict
from veridoc.review.evidence import verify_evidence_bundle
from veridoc.review.models import IdempotentRequest, build_review_snapshot
from veridoc.review.persistence.cli import main
from veridoc.review.persistence.sqlite import SQLiteReviewRepository


def _create_case(repository: SQLiteReviewRepository, key: str) -> str:
    result = ProcessingResult(
        extraction=InvoiceExtraction(document_type="invoice"),
        verdict=ProcessingVerdict(
            status="clear",
            summary="No deterministic verification findings require review.",
            finding_count=0,
        ),
    )
    return repository.create_case(
        snapshot=build_review_snapshot(result),
        creator_actor_id="reviewer-1",
        request_id=f"request-{key}",
        idempotent_request=IdempotentRequest(
            actor_id="reviewer-1",
            operation="create_case",
            idempotency_key=key,
            request_digest="a" * 64,
        ),
    ).case_id


def _database(tmp_path: Path) -> tuple[SQLiteReviewRepository, str]:
    repository = SQLiteReviewRepository(tmp_path / "review.sqlite")
    repository.initialize()
    return repository, _create_case(repository, "evidence-key")


def test_cli_export_writes_a_verifiable_bundle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, case_id = _database(tmp_path)
    output = tmp_path / "case-evidence.json"

    status = main(
        [
            "--database",
            str(tmp_path / "review.sqlite"),
            "export",
            "--case-id",
            case_id,
            "--output",
            str(output),
        ]
    )

    assert status == 0
    assert f"Evidence bundle exported for case {case_id}." in capsys.readouterr().out
    verified = verify_evidence_bundle(output.read_bytes())
    assert verified.case.case_id == case_id
    assert verified.exported_by == "operator"


def test_cli_export_records_the_configured_exporter(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, case_id = _database(tmp_path)
    output = tmp_path / "case-evidence.json"

    status = main(
        [
            "--database",
            str(tmp_path / "review.sqlite"),
            "export",
            "--case-id",
            case_id,
            "--output",
            str(output),
            "--exported-by",
            "reviewer-1",
        ]
    )

    assert status == 0
    capsys.readouterr()
    assert verify_evidence_bundle(output.read_bytes()).exported_by == "reviewer-1"


def test_cli_export_reports_unknown_cases(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = SQLiteReviewRepository(tmp_path / "review.sqlite")
    repository.initialize()

    status = main(
        [
            "--database",
            str(tmp_path / "review.sqlite"),
            "export",
            "--case-id",
            "unknown-case",
            "--output",
            str(tmp_path / "case-evidence.json"),
        ]
    )

    assert status == 1
    assert "No review case exists" in capsys.readouterr().err


def test_cli_export_rejects_invalid_exporter_identities(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, case_id = _database(tmp_path)

    status = main(
        [
            "--database",
            str(tmp_path / "review.sqlite"),
            "export",
            "--case-id",
            case_id,
            "--output",
            str(tmp_path / "case-evidence.json"),
            "--exported-by",
            "not an identity",
        ]
    )

    assert status == 1
    assert "exporter identity is invalid" in capsys.readouterr().err


def test_cli_export_reports_unwritable_outputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, case_id = _database(tmp_path)

    status = main(
        [
            "--database",
            str(tmp_path / "review.sqlite"),
            "export",
            "--case-id",
            case_id,
            "--output",
            str(tmp_path / "missing-dir" / "case-evidence.json"),
        ]
    )

    assert status == 1
    assert "could not be written" in capsys.readouterr().err


def test_cli_verify_bundle_accepts_an_exported_bundle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, case_id = _database(tmp_path)
    output = tmp_path / "case-evidence.json"
    assert (
        main(
            [
                "--database",
                str(tmp_path / "review.sqlite"),
                "export",
                "--case-id",
                case_id,
                "--output",
                str(output),
            ]
        )
        == 0
    )
    capsys.readouterr()

    status = main(["verify-bundle", "--input", str(output)])

    assert status == 0
    out = capsys.readouterr().out
    assert f"Evidence bundle verified: case {case_id}" in out
    assert "status unassigned" in out


def test_cli_verify_bundle_rejects_tampered_bundles(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, case_id = _database(tmp_path)
    output = tmp_path / "case-evidence.json"
    assert (
        main(
            [
                "--database",
                str(tmp_path / "review.sqlite"),
                "export",
                "--case-id",
                case_id,
                "--output",
                str(output),
            ]
        )
        == 0
    )
    capsys.readouterr()
    payload = json.loads(output.read_text(encoding="utf-8"))
    payload["case"]["status"] = "decided"
    output.write_bytes(json.dumps(payload).encode("utf-8"))

    status = main(["verify-bundle", "--input", str(output)])

    assert status == 1
    assert "not verifiable" in capsys.readouterr().err


def test_cli_verify_bundle_reports_missing_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    status = main(["verify-bundle", "--input", str(tmp_path / "missing.json")])

    assert status == 1
    assert "could not be read" in capsys.readouterr().err


def test_cli_verify_bundle_reports_non_json_inputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_bytes(b"not-json-bytes")

    status = main(["verify-bundle", "--input", str(bundle_path)])

    assert status == 1
    assert "not verifiable" in capsys.readouterr().err
