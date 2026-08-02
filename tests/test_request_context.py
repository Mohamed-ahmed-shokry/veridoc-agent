"""Request-correlation and safe operational logging tests."""

from __future__ import annotations

import logging
import re

import httpx
import pytest

from veridoc.app import app


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


@pytest.mark.anyio
async def test_request_context_echoes_a_safe_correlation_identifier(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="veridoc.request")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/health?document=never-log-this", headers={"X-Request-ID": "trace-42"}
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "trace-42"
    assert "request_id=trace-42" in caplog.text
    assert "path=/health" in caplog.text
    assert "never-log-this" not in caplog.text


@pytest.mark.anyio
async def test_request_context_replaces_unsafe_identifiers_on_error_responses() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/missing", headers={"X-Request-ID": "unsafe value"}
        )

    assert response.status_code == 404
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["X-Request-ID"])
