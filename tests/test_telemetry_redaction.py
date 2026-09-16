"""Telemetry redaction tests for every operational sink.

A single set of ``restricted`` fixture values (ADR 0012) is driven through
every untrusted request position — query text, unknown paths, filenames,
multipart bodies, JSON bodies, and bearer credentials — and must appear in
none of the telemetry sinks: request logs, structured JSON records,
``/metrics`` output, or error response bodies.
"""

import json
import logging
from io import BytesIO

import httpx
import pytest
from PIL import Image

from veridoc.app import app
from veridoc.telemetry.registry import REGISTRY

RESTRICTED_MARKER = "restricted-marker-9f3a"
RESTRICTED_SECRET = "restricted-secret-9f3a"
RESTRICTED_DOCUMENT = "restricted-invoice-ACME-9f3a"
RESTRICTED_SESSION = "restricted-session-token-9f3a"
RESTRICTED_PATH = "restricted-tmp-path-9f3a"

RESTRICTED_VALUES = (
    RESTRICTED_MARKER,
    RESTRICTED_SECRET,
    RESTRICTED_DOCUMENT,
    RESTRICTED_SESSION,
    RESTRICTED_PATH,
)


@pytest.fixture(autouse=True)
def _reset_registry():
    REGISTRY.reset()
    yield
    REGISTRY.reset()


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (12, 8), color="white").save(output, format="PNG")
    return output.getvalue()


def _assert_absent(payload: str, sink: str) -> None:
    for value in RESTRICTED_VALUES:
        assert value not in payload, f"{value!r} leaked into {sink}"


@pytest.mark.anyio
async def test_restricted_values_never_reach_request_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Request logs carry templates and codes, never untrusted values."""
    caplog.set_level(logging.INFO, logger="veridoc.request")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get(f"/{RESTRICTED_MARKER}?document={RESTRICTED_DOCUMENT}")
        await client.get("/health", headers={"X-Custom-Secret": RESTRICTED_SECRET})
        await client.get(f"/review/cases/{RESTRICTED_SESSION}")
        await client.post(
            "/ocr",
            files={
                "file": (
                    f"{RESTRICTED_MARKER}.png",
                    _png_bytes(),
                    "image/png",
                )
            },
        )
        await client.post(
            "/admin/reference-data/invoices",
            headers={"Authorization": f"Bearer {RESTRICTED_SECRET}"},
            json={"vendor_key": RESTRICTED_DOCUMENT},
        )

    _assert_absent(caplog.text, "request logs")


@pytest.mark.anyio
async def test_restricted_values_never_reach_json_telemetry(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Structured JSON records carry operational fields only."""
    monkeypatch.setenv("VERIDOC_TELEMETRY_JSON", "1")
    caplog.set_level(logging.INFO, logger="veridoc.telemetry")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get(f"/{RESTRICTED_MARKER}?document={RESTRICTED_DOCUMENT}")
        await client.post(
            "/ocr",
            files={
                "file": (
                    f"{RESTRICTED_MARKER}.png",
                    RESTRICTED_DOCUMENT.encode("utf-8"),
                    "image/png",
                )
            },
        )

    assert caplog.records, "expected JSON telemetry records"
    for record in caplog.records:
        payload = json.loads(record.getMessage())
        assert set(payload) == {
            "request_id",
            "method",
            "route",
            "status_code",
            "duration_ms",
        }
    _assert_absent(caplog.text, "JSON telemetry")


@pytest.mark.anyio
async def test_restricted_values_never_reach_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Metric labels and values never contain untrusted request data."""
    monkeypatch.setenv("VERIDOC_METRICS_ENABLED", "1")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get(f"/{RESTRICTED_MARKER}?document={RESTRICTED_DOCUMENT}")
        await client.get(f"/review/cases/{RESTRICTED_SESSION}")
        response = await client.get("/metrics")

    assert response.status_code == 200
    _assert_absent(response.text, "/metrics output")
    assert RESTRICTED_MARKER not in json.dumps(response.json()["requests_by_route"])


@pytest.mark.anyio
async def test_restricted_values_never_reach_error_bodies() -> None:
    """Safe error contracts never echo untrusted submitted data."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        validation_error = await client.post(
            "/ocr",
            files={
                "file": (
                    f"{RESTRICTED_MARKER}.png",
                    RESTRICTED_DOCUMENT.encode("utf-8"),
                    "text/plain",
                )
            },
        )
        auth_error = await client.post(
            "/review/session",
            headers={"Authorization": f"Bearer {RESTRICTED_SESSION}"},
        )
        admin_error = await client.get(
            "/admin/reference-data/invoices",
            headers={"Authorization": f"Bearer {RESTRICTED_SECRET}"},
        )

    assert validation_error.status_code == 415
    _assert_absent(validation_error.text, "validation error body")
    _assert_absent(auth_error.text, "session error body")
    _assert_absent(admin_error.text, "administration error body")
