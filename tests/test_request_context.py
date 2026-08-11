"""Request-correlation and safe operational logging tests."""

from __future__ import annotations

import logging
import re
from io import BytesIO

import httpx
import pytest
from PIL import Image

from veridoc.app import app, get_ocr_engine


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (12, 8), color="white").save(output, format="PNG")
    return output.getvalue()


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


@pytest.mark.anyio
async def test_unexpected_errors_return_a_safe_correlated_response() -> None:
    def fail_without_exposing_details() -> None:
        raise RuntimeError("sensitive internal detail")

    app.dependency_overrides[get_ocr_engine] = fail_without_exposing_details
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/ocr",
                files={"file": ("invoice.png", _png_bytes(), "image/png")},
                headers={"X-Request-ID": "failed-request"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json() == {
        "detail": {
            "code": "internal_server_error",
            "message": "An unexpected server error occurred.",
        }
    }
    assert response.headers["X-Request-ID"] == "failed-request"
    assert "sensitive internal detail" not in response.text
