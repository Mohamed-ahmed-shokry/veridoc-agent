"""Operational telemetry tests: registry, JSON export, and /metrics."""

import json
import logging

import httpx
import pytest

from veridoc.app import app
from veridoc.telemetry.log import emit_request_record, telemetry_json_enabled
from veridoc.telemetry.registry import REGISTRY, TelemetryRegistry


@pytest.fixture(autouse=True)
def _reset_registry():
    REGISTRY.reset()
    yield
    REGISTRY.reset()


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


def test_registry_counts_requests_by_route_and_status_class() -> None:
    """Requests aggregate under static templates and 2xx/4xx/5xx classes."""
    registry = TelemetryRegistry()
    registry.record_request("/health", 200)
    registry.record_request("/health", 200)
    registry.record_request("/review/cases/{case_id}", 404)
    registry.record_request("/ocr", 503)

    snapshot = registry.snapshot()

    assert snapshot["requests_total"] == 4
    assert snapshot["requests_by_route"] == {
        "/health": {"2xx": 2},
        "/review/cases/{case_id}": {"4xx": 1},
        "/ocr": {"5xx": 1},
    }


def test_registry_counts_scan_outcomes() -> None:
    """Scan outcomes aggregate under their three typed buckets."""
    registry = TelemetryRegistry()
    registry.record_scan_outcome("clean")
    registry.record_scan_outcome("rejected")
    registry.record_scan_outcome("unavailable")
    registry.record_scan_outcome("clean")

    assert registry.snapshot()["scans"] == {
        "clean": 2,
        "rejected": 1,
        "unavailable": 1,
    }


def test_registry_rejects_unknown_scan_outcomes() -> None:
    """Unknown scan outcomes raise instead of corrupting the counters."""
    registry = TelemetryRegistry()
    with pytest.raises(ValueError, match="Unknown scan outcome"):
        registry.record_scan_outcome("suspicious")


def test_registry_counts_rate_limit_rejections() -> None:
    """Rate-limit rejections aggregate into one counter."""
    registry = TelemetryRegistry()
    registry.record_rate_limited()
    registry.record_rate_limited()

    assert registry.snapshot()["rate_limited_total"] == 2


def test_registry_snapshot_reports_uptime_and_storage() -> None:
    """Snapshots carry uptime and aggregate temporary-storage figures."""
    snapshot = TelemetryRegistry().snapshot()

    assert snapshot["uptime_seconds"] >= 0
    storage = snapshot["temporary_storage"]
    assert set(storage) == {"total_bytes", "used_bytes", "free_bytes"}
    assert all(isinstance(value, int) for value in storage.values())


def test_registry_reset_clears_every_counter() -> None:
    """Reset returns the registry to its initial aggregate state."""
    registry = TelemetryRegistry()
    registry.record_request("/health", 200)
    registry.record_scan_outcome("clean")
    registry.record_rate_limited()

    registry.reset()
    snapshot = registry.snapshot()

    assert snapshot["requests_total"] == 0
    assert snapshot["requests_by_route"] == {}
    assert snapshot["scans"] == {"clean": 0, "rejected": 0, "unavailable": 0}
    assert snapshot["rate_limited_total"] == 0


def test_telemetry_json_flag_defaults_to_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Structured JSON export stays off unless explicitly enabled."""
    monkeypatch.delenv("VERIDOC_TELEMETRY_JSON", raising=False)
    assert telemetry_json_enabled() is False
    assert telemetry_json_enabled({}) is False
    assert telemetry_json_enabled({"VERIDOC_TELEMETRY_JSON": "1"}) is True
    assert telemetry_json_enabled({"VERIDOC_TELEMETRY_JSON": "0"}) is False


def test_emit_request_record_is_a_noop_when_disabled(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Disabled export emits no telemetry log records."""
    monkeypatch.delenv("VERIDOC_TELEMETRY_JSON", raising=False)
    caplog.set_level(logging.INFO, logger="veridoc.telemetry")

    emit_request_record(
        request_id="trace-1",
        method="GET",
        route="/health",
        status_code=200,
        duration_ms=1.5,
    )

    assert caplog.text == ""


def test_emit_request_record_writes_one_json_line(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Enabled export emits exactly the approved operational fields."""
    monkeypatch.setenv("VERIDOC_TELEMETRY_JSON", "1")
    caplog.set_level(logging.INFO, logger="veridoc.telemetry")

    emit_request_record(
        request_id="trace-1",
        method="GET",
        route="/health",
        status_code=200,
        duration_ms=1.54,
    )

    payload = json.loads(caplog.records[-1].getMessage())
    assert payload == {
        "request_id": "trace-1",
        "method": "GET",
        "route": "/health",
        "status_code": 200,
        "duration_ms": 1.5,
    }


@pytest.mark.anyio
async def test_requests_are_counted_through_the_app() -> None:
    """Real requests aggregate under their static route templates."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/health")
        await client.get("/health")
        await client.get("/missing-route")

    snapshot = REGISTRY.snapshot()
    assert snapshot["requests_total"] == 3
    assert snapshot["requests_by_route"]["/health"] == {"2xx": 2}
    assert snapshot["requests_by_route"]["<unmatched>"] == {"4xx": 1}


@pytest.mark.anyio
async def test_case_routes_count_under_templates_not_identifiers() -> None:
    """Case identifiers never become metric labels."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/review/cases/private-case-1")
        await client.get("/review/cases/private-case-2")

    routes = REGISTRY.snapshot()["requests_by_route"]
    assert routes == {"/review/cases/{case_id}": {"4xx": 2}}
    assert "private-case-1" not in json.dumps(routes)
    assert "private-case-2" not in json.dumps(routes)


@pytest.mark.anyio
async def test_metrics_endpoint_is_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the enable flag /metrics answers 404 like an unknown route."""
    monkeypatch.delenv("VERIDOC_METRICS_ENABLED", raising=False)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/metrics")

    assert response.status_code == 404


@pytest.mark.anyio
async def test_metrics_endpoint_exports_operational_counters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Enabled /metrics returns the typed aggregate snapshot."""
    monkeypatch.setenv("VERIDOC_METRICS_ENABLED", "1")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/health")
        await client.get("/missing-route")
        response = await client.get("/metrics")

    assert response.status_code == 200
    body = response.json()
    assert body["requests_total"] == 2
    assert body["requests_by_route"] == {
        "/health": {"2xx": 1},
        "<unmatched>": {"4xx": 1},
    }
    assert body["scans"] == {"clean": 0, "rejected": 0, "unavailable": 0}
    assert body["rate_limited_total"] == 0
    assert body["uptime_seconds"] >= 0
    assert set(body["temporary_storage"]) == {
        "total_bytes",
        "used_bytes",
        "free_bytes",
    }


@pytest.mark.anyio
async def test_metrics_endpoint_counts_rate_limit_rejections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """429 rejections surface through the shared rate-limited counter."""
    monkeypatch.setenv("VERIDOC_METRICS_ENABLED", "1")
    monkeypatch.setenv("VERIDOC_RATE_LIMIT_CAPACITY", "1")
    monkeypatch.setenv("VERIDOC_RATE_LIMIT_REFILL_PER_SECOND", "0")
    transport = httpx.ASGITransport(app=app, client=("10.8.8.8", 1))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/missing-one")).status_code == 404
        assert (await client.get("/missing-two")).status_code == 429
        response = await client.get("/metrics")

    assert response.status_code == 200
    assert response.json()["rate_limited_total"] == 1


def test_metrics_endpoint_declares_typed_response_schema() -> None:
    """OpenAPI identifies the metrics response through its named schema."""
    openapi = app.openapi()
    response_schema = openapi["paths"]["/metrics"]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]
    assert response_schema == {"$ref": "#/components/schemas/MetricsResponse"}
    assert openapi["components"]["schemas"]["MetricsResponse"]["required"] == [
        "requests_total",
        "requests_by_route",
        "scans",
        "rate_limited_total",
        "uptime_seconds",
        "temporary_storage",
    ]
