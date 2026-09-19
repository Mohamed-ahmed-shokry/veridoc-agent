"""Tests for artifact and provider identity capture and drift detection."""

from __future__ import annotations

from pathlib import Path

from veridoc.evaluation.identity import (
    capture_artifact_identity,
    capture_provider_identity,
    detect_artifact_drift,
    detect_provider_drift,
)
from veridoc.evaluation.models import ArtifactIdentityRecord, ProviderIdentityRecord


def test_capture_artifact_identity(tmp_path: Path) -> None:
    identity = capture_artifact_identity()
    assert identity.app_version == "0.1.0"
    assert identity.reference_schema_version == 5
    assert identity.review_schema_version == 4
    assert len(identity.lockfile_sha256) == 64
    assert identity.python_version


def test_capture_provider_identity() -> None:
    identity = capture_provider_identity(
        model_name="test-model",
        system_prompt="Test prompt",
    )
    assert identity.model_name == "test-model"
    assert len(identity.system_prompt_sha256) == 64
    assert len(identity.extraction_schema_sha256) == 64


def test_detect_artifact_drift() -> None:
    baseline = ArtifactIdentityRecord(
        app_version="0.1.0",
        git_commit="a" * 40,
        python_version="3.12.0",
        platform="win32",
        lockfile_sha256="1" * 64,
        tesseract_version="5.3.0",
        tessdata_sha256={},
        reference_schema_version=4,
        review_schema_version=4,
    )
    # No drift
    assert detect_artifact_drift(baseline, baseline) == []

    # Commit and schema changed
    mutated = baseline.model_copy(
        update={
            "git_commit": "b" * 40,
            "reference_schema_version": 5,
        }
    )
    drift = detect_artifact_drift(baseline, mutated)
    assert len(drift) == 2
    assert any("git_commit changed" in d for d in drift)
    assert any("reference_schema_version changed" in d for d in drift)


def test_detect_provider_drift() -> None:
    baseline = ProviderIdentityRecord(
        model_name="gpt-4o-mini",
        system_prompt_sha256="a" * 64,
        extraction_schema_sha256="b" * 64,
    )
    assert detect_provider_drift(baseline, baseline) == []

    mutated = baseline.model_copy(
        update={
            "model_name": "gpt-4o",
            "system_prompt_sha256": "c" * 64,
        }
    )
    drift = detect_provider_drift(baseline, mutated)
    assert len(drift) == 2
    assert any("model_name changed" in d for d in drift)
    assert any("system_prompt_sha256 changed" in d for d in drift)
