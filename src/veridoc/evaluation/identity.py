"""Artifact and provider identity capture and drift detection."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Final

import veridoc
from veridoc.evaluation.manifest import compute_file_sha256
from veridoc.evaluation.models import ArtifactIdentityRecord, ProviderIdentityRecord
from veridoc.extraction.models import InvoiceExtraction
from veridoc.persistence.migrations import LATEST_SCHEMA_VERSION as LATEST_REF_SCHEMA
from veridoc.review.persistence.migrations import (
    LATEST_SCHEMA_VERSION as LATEST_REV_SCHEMA,
)

DEFAULT_SYSTEM_PROMPT: Final[str] = (
    "Extract structured invoice information and page-level evidence strictly conforming to the schema."
)


def _get_git_commit(repo_root: Path) -> str:
    env_commit = os.environ.get("GIT_COMMIT", "").strip()
    if env_commit:
        return env_commit
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        commit = res.stdout.strip()
        if commit:
            return commit
    except (subprocess.SubprocessError, OSError, UnicodeError):
        return "unknown"
    return "unknown"


def _get_tesseract_version() -> str:
    try:
        import pytesseract

        return str(pytesseract.get_tesseract_version()).strip()
    except (ImportError, OSError, RuntimeError, ValueError):
        return "unavailable"


def _get_tessdata_hashes() -> dict[str, str]:
    prefix = os.environ.get("TESSDATA_PREFIX", "").strip()
    if not prefix:
        return {}
    prefix_path = Path(prefix)
    if not (prefix_path.exists() and prefix_path.is_dir()):
        return {}
    hashes: dict[str, str] = {}
    for traineddata in sorted(prefix_path.glob("*.traineddata")):
        lang = traineddata.stem
        hashes[lang] = compute_file_sha256(traineddata)
    return hashes


def capture_artifact_identity(repo_root: Path | None = None) -> ArtifactIdentityRecord:
    """Capture the immutable runtime and code artifact identity of the system."""
    root = repo_root or Path(__file__).resolve().parents[3]
    lock_path = root / "uv.lock"
    lock_hash = compute_file_sha256(lock_path) if lock_path.is_file() else "0" * 64

    return ArtifactIdentityRecord(
        app_version=veridoc.__version__,
        git_commit=_get_git_commit(root),
        python_version=sys.version.split()[0],
        platform=sys.platform,
        lockfile_sha256=lock_hash,
        tesseract_version=_get_tesseract_version(),
        tessdata_sha256=_get_tessdata_hashes(),
        reference_schema_version=LATEST_REF_SCHEMA,
        review_schema_version=LATEST_REV_SCHEMA,
    )


def capture_provider_identity(
    *,
    model_name: str | None = None,
    system_prompt: str | None = None,
    extraction_schema: str | None = None,
) -> ProviderIdentityRecord:
    """Capture the model, prompt, and output schema identity for structured extraction."""
    resolved_model = (
        model_name
        or os.environ.get("VERIDOC_LLM_MODEL", "").strip()
        or "deterministic-baseline"
    )

    prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    schema_str = (
        extraction_schema
        if extraction_schema is not None
        else json.dumps(InvoiceExtraction.model_json_schema(), sort_keys=True)
    )
    schema_hash = hashlib.sha256(schema_str.encode("utf-8")).hexdigest()

    return ProviderIdentityRecord(
        model_name=resolved_model,
        system_prompt_sha256=prompt_hash,
        extraction_schema_sha256=schema_hash,
    )


def detect_artifact_drift(
    baseline: ArtifactIdentityRecord,
    current: ArtifactIdentityRecord,
) -> list[str]:
    """Compare baseline artifact identity with current identity, returning detected drift warnings."""
    drift: list[str] = []
    if baseline.app_version != current.app_version:
        drift.append(
            f"app_version changed from {baseline.app_version} to {current.app_version}"
        )
    if baseline.git_commit != current.git_commit:
        drift.append(
            f"git_commit changed from {baseline.git_commit} to {current.git_commit}"
        )
    if baseline.python_version != current.python_version:
        drift.append(
            f"python_version changed from {baseline.python_version} to {current.python_version}"
        )
    if baseline.platform != current.platform:
        drift.append(f"platform changed from {baseline.platform} to {current.platform}")
    if baseline.lockfile_sha256 != current.lockfile_sha256:
        drift.append(
            f"lockfile_sha256 changed from {baseline.lockfile_sha256} to {current.lockfile_sha256}"
        )
    if baseline.tesseract_version != current.tesseract_version:
        drift.append(
            f"tesseract_version changed from {baseline.tesseract_version} to {current.tesseract_version}"
        )
    if baseline.tessdata_sha256 != current.tessdata_sha256:
        drift.append(
            f"tessdata_sha256 changed from {baseline.tessdata_sha256} to {current.tessdata_sha256}"
        )
    if baseline.reference_schema_version != current.reference_schema_version:
        drift.append(
            f"reference_schema_version changed from {baseline.reference_schema_version} to {current.reference_schema_version}"
        )
    if baseline.review_schema_version != current.review_schema_version:
        drift.append(
            f"review_schema_version changed from {baseline.review_schema_version} to {current.review_schema_version}"
        )
    return drift


def detect_provider_drift(
    baseline: ProviderIdentityRecord,
    current: ProviderIdentityRecord,
) -> list[str]:
    """Compare baseline provider identity with current identity, returning detected drift warnings."""
    drift: list[str] = []
    if baseline.model_name != current.model_name:
        drift.append(
            f"model_name changed from {baseline.model_name} to {current.model_name}"
        )
    if baseline.system_prompt_sha256 != current.system_prompt_sha256:
        drift.append(
            f"system_prompt_sha256 changed from {baseline.system_prompt_sha256} to {current.system_prompt_sha256}"
        )
    if baseline.extraction_schema_sha256 != current.extraction_schema_sha256:
        drift.append(
            f"extraction_schema_sha256 changed from {baseline.extraction_schema_sha256} to {current.extraction_schema_sha256}"
        )
    return drift
