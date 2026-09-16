"""Environment-sourced configuration for the scanning boundary."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from veridoc.scanning.protocol import ScanUnavailableError

_DEFAULT_CLAMD_HOST = "127.0.0.1"
_DEFAULT_CLAMD_PORT = 3310
_DEFAULT_CLAMD_TIMEOUT_SECONDS = 30.0
_DEFAULT_QUARANTINE_RETENTION_DAYS = 30
_MAX_TIMEOUT_SECONDS = 300.0
_ENABLED_VALUES = frozenset({"1", "true", "yes"})


@dataclass(frozen=True, slots=True)
class ScanningSettings:
    """Required configuration for the scanning boundary when it is enabled."""

    enabled: bool
    clamd_host: str = _DEFAULT_CLAMD_HOST
    clamd_port: int = _DEFAULT_CLAMD_PORT
    clamd_timeout_seconds: float = _DEFAULT_CLAMD_TIMEOUT_SECONDS
    quarantine_directory: str = ""
    quarantine_retention_days: int = _DEFAULT_QUARANTINE_RETENTION_DAYS

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> ScanningSettings:
        """Load non-empty scanning settings, failing closed on bad values."""
        values = os.environ if environment is None else environment
        if not _enabled(values.get("VERIDOC_SCAN_ENABLED")):
            return cls(enabled=False)
        return cls(
            enabled=True,
            clamd_host=_host(values.get("VERIDOC_CLAMD_HOST")),
            clamd_port=_port(values.get("VERIDOC_CLAMD_PORT")),
            clamd_timeout_seconds=_timeout(values.get("VERIDOC_CLAMD_TIMEOUT_SECONDS")),
            quarantine_directory=_quarantine_directory(
                values.get("VERIDOC_QUARANTINE_DIRECTORY")
            ),
            quarantine_retention_days=_retention_days(
                values.get("VERIDOC_QUARANTINE_RETENTION_DAYS")
            ),
        )


def _enabled(raw_value: str | None) -> bool:
    if raw_value is None or not raw_value.strip():
        return False
    normalized = raw_value.strip().lower()
    if normalized in _ENABLED_VALUES:
        return True
    raise ScanUnavailableError


def _host(raw_value: str | None) -> str:
    host = (raw_value or "").strip()
    if not host:
        return _DEFAULT_CLAMD_HOST
    return host


def _port(raw_value: str | None) -> int:
    if raw_value is None or not raw_value.strip():
        return _DEFAULT_CLAMD_PORT
    try:
        parsed = int(raw_value)
    except ValueError:
        raise ScanUnavailableError from None
    if not 1 <= parsed <= 65535:
        raise ScanUnavailableError
    return parsed


def _timeout(raw_value: str | None) -> float:
    if raw_value is None or not raw_value.strip():
        return _DEFAULT_CLAMD_TIMEOUT_SECONDS
    try:
        timeout = float(raw_value)
    except (TypeError, ValueError):
        raise ScanUnavailableError from None
    if not isfinite(timeout) or not 0 < timeout <= _MAX_TIMEOUT_SECONDS:
        raise ScanUnavailableError
    return timeout


def _quarantine_directory(raw_value: str | None) -> str:
    directory = (raw_value or "").strip()
    if not directory:
        raise ScanUnavailableError
    candidate = Path(directory)
    if not candidate.exists() or not candidate.is_dir():
        raise ScanUnavailableError
    return directory


def _retention_days(raw_value: str | None) -> int:
    if raw_value is None or not raw_value.strip():
        return _DEFAULT_QUARANTINE_RETENTION_DAYS
    try:
        parsed = int(raw_value)
    except ValueError:
        raise ScanUnavailableError from None
    if parsed <= 0:
        raise ScanUnavailableError
    return parsed
