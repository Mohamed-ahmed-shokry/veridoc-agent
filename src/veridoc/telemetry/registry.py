"""Thread-safe in-memory registry for operational counters.

The registry aggregates request counts by static route template and status
class, scanner outcomes, and rate-limit rejections. Snapshots contain plain
JSON-serializable operational values only: no path parameters, query text,
headers, bodies, or secrets ever enter the registry.
"""

from __future__ import annotations

import shutil
import tempfile
import time
from threading import Lock

_STARTED_AT = time.monotonic()


def _status_class(status_code: int) -> str:
    if 200 <= status_code < 300:
        return "2xx"
    if 400 <= status_code < 500:
        return "4xx"
    return "5xx"


class TelemetryRegistry:
    """Aggregate operational counters with a JSON-safe snapshot."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._requests: dict[str, dict[str, int]] = {}
        self._scans = {"clean": 0, "rejected": 0, "unavailable": 0}
        self._rate_limited = 0

    def record_request(self, route: str, status_code: int) -> None:
        """Count one completed request under its static route template."""
        with self._lock:
            classes = self._requests.setdefault(route, {})
            key = _status_class(status_code)
            classes[key] = classes.get(key, 0) + 1

    def record_scan_outcome(self, outcome: str) -> None:
        """Count one scan outcome: ``clean``, ``rejected``, or ``unavailable``."""
        if outcome not in self._scans:
            raise ValueError(f"Unknown scan outcome: {outcome!r}.")
        with self._lock:
            self._scans[outcome] += 1

    def record_rate_limited(self) -> None:
        """Count one 429 rate-limit rejection."""
        with self._lock:
            self._rate_limited += 1

    def reset(self) -> None:
        """Clear every counter; used by tests only."""
        with self._lock:
            self._requests = {}
            self._scans = {"clean": 0, "rejected": 0, "unavailable": 0}
            self._rate_limited = 0

    def snapshot(self) -> dict[str, object]:
        """Return the aggregate operational counters and storage figures."""
        with self._lock:
            requests = {
                route: dict(classes) for route, classes in self._requests.items()
            }
            scans = dict(self._scans)
            rate_limited = self._rate_limited
        return {
            "requests_total": sum(
                sum(classes.values()) for classes in requests.values()
            ),
            "requests_by_route": requests,
            "scans": scans,
            "rate_limited_total": rate_limited,
            "uptime_seconds": round(time.monotonic() - _STARTED_AT, 1),
            "temporary_storage": _temporary_storage_figures(),
        }


def _temporary_storage_figures() -> dict[str, int]:
    try:
        usage = shutil.disk_usage(tempfile.gettempdir())
    except OSError:
        return {"total_bytes": 0, "used_bytes": 0, "free_bytes": 0}
    return {
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
    }


REGISTRY = TelemetryRegistry()
"""The process-wide operational counter registry."""
