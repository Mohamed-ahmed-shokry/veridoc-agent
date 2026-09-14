"""Deterministic readiness checks for the Phase 10 deployment profile.

Readiness is a configuration and local-store signal, not a liveness probe:
`GET /health` keeps reporting process liveness while `GET /ready` reports
whether every *configured* dependency is present and locally usable. Checks
never start network providers, scan files, or open SQLite write transactions;
they are pure functions over the process environment plus cheap filesystem
inspections and the existing review configuration validators.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from veridoc.review.config import (
    ReviewActorDirectory,
    ReviewAuthenticationUnavailableError,
    ReviewOriginSettings,
)

_DEFAULT_REFERENCE_DATABASE = "veridoc-reference.sqlite3"
_DEFAULT_REVIEW_DATABASE = "veridoc-review.sqlite3"


@dataclass(frozen=True, slots=True)
class ReadinessCheck:
    """One named, deterministic readiness check result."""

    name: str
    ok: bool


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    """The aggregate readiness signal and every evaluated check."""

    ready: bool
    checks: tuple[ReadinessCheck, ...]

    def as_dict(self) -> dict[str, bool]:
        """Return check names and outcomes as a plain mapping."""
        return {check.name: check.ok for check in self.checks}


def readiness_from_environment(
    environment: Mapping[str, str] | None = None,
) -> ReadinessResult:
    """Evaluate every configured readiness check without starting providers."""
    values = os.environ if environment is None else environment
    checks = (
        _reference_store_check(values),
        _review_store_check(values),
        _review_identity_check(values),
        _extraction_provider_check(values),
    )
    return ReadinessResult(
        ready=all(check.ok for check in checks),
        checks=checks,
    )


def _reference_store_check(values: Mapping[str, str]) -> ReadinessCheck:
    path = values.get("VERIDOC_REFERENCE_DATABASE", _DEFAULT_REFERENCE_DATABASE)
    return ReadinessCheck(
        "reference_store", _store_ready(path.strip() or _DEFAULT_REFERENCE_DATABASE)
    )


def _review_store_check(values: Mapping[str, str]) -> ReadinessCheck:
    path = values.get("VERIDOC_REVIEW_DATABASE", _DEFAULT_REVIEW_DATABASE)
    return ReadinessCheck(
        "review_store", _store_ready(path.strip() or _DEFAULT_REVIEW_DATABASE)
    )


def _review_identity_check(values: Mapping[str, str]) -> ReadinessCheck:
    configured = bool(
        values.get("VERIDOC_REVIEW_ACTORS_FILE") or values.get("VERIDOC_REVIEW_ORIGIN")
    )
    if not configured:
        return ReadinessCheck("review_identity", True)
    try:
        ReviewActorDirectory.from_environment(values)
        ReviewOriginSettings.from_environment(values)
    except ReviewAuthenticationUnavailableError:
        return ReadinessCheck("review_identity", False)
    return ReadinessCheck("review_identity", True)


def _extraction_provider_check(values: Mapping[str, str]) -> ReadinessCheck:
    configured = bool(values.get("OPENAI_API_KEY") or values.get("VERIDOC_LLM_MODEL"))
    if not configured:
        return ReadinessCheck("extraction_provider", True)
    complete = bool(
        values.get("OPENAI_API_KEY", "").strip()
        and values.get("VERIDOC_LLM_MODEL", "").strip()
    )
    return ReadinessCheck("extraction_provider", complete)


def _store_ready(path: str) -> bool:
    """Return whether a SQLite path can be created or written at request time.

    The path must not be an existing directory, and its parent directory must
    exist so later repository initialization can create the file. This never
    opens or mutates the database.
    """
    candidate = Path(path)
    if candidate.is_dir():
        return False
    parent = candidate.parent
    return parent.exists() and parent.is_dir()
