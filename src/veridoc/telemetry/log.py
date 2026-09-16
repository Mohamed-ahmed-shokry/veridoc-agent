"""Structured operational request records for log export.

When ``VERIDOC_TELEMETRY_JSON`` is ``1``, every completed request also emits
one JSON line to the ``veridoc.telemetry`` logger. The record carries the
same operational fields as the metadata-only completion log — correlation
ID, method, static route template, status code, duration — and nothing else.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping

_TELEMETRY_LOGGER = logging.getLogger("veridoc.telemetry")


def telemetry_json_enabled(environment: Mapping[str, str] | None = None) -> bool:
    """Return whether structured JSON request records are enabled."""
    values = os.environ if environment is None else environment
    return values.get("VERIDOC_TELEMETRY_JSON", "").strip() == "1"


def emit_request_record(
    *,
    request_id: str,
    method: str,
    route: str,
    status_code: int,
    duration_ms: float,
) -> None:
    """Emit one JSON request record when structured export is enabled."""
    if not telemetry_json_enabled():
        return
    _TELEMETRY_LOGGER.info(
        "%s",
        json.dumps(
            {
                "request_id": request_id,
                "method": method,
                "route": route,
                "status_code": status_code,
                "duration_ms": round(duration_ms, 1),
            },
            sort_keys=True,
        ),
    )
