"""Pre-parser request-body limit tests."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from veridoc.app import app, get_ocr_engine


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("path", "limit_name", "code"),
    [
        ("/ocr", "MAX_DOCUMENT_REQUEST_BYTES", "upload_too_large"),
        (
            "/admin/reference-data/import",
            "MAX_ADMIN_IMPORT_REQUEST_BYTES",
            "reference_data_import_too_large",
        ),
    ],
)
async def test_declared_oversized_bodies_are_rejected_before_routing(
    path: str,
    limit_name: str,
    code: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(f"veridoc.app.{limit_name}", 10)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            path,
            content=b"",
            headers={
                "Content-Length": "11",
                "Content-Type": "multipart/form-data; boundary=fixture",
                "X-Request-ID": "declared-limit",
            },
        )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == code
    assert response.headers["X-Request-ID"] == "declared-limit"


@pytest.mark.anyio
async def test_streamed_oversized_body_is_rejected_without_content_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dependency_resolved = False

    def unexpected_ocr_engine() -> None:
        nonlocal dependency_resolved
        dependency_resolved = True

    async def chunks() -> AsyncIterator[bytes]:
        yield b"a" * 6
        yield b"b" * 5

    monkeypatch.setattr("veridoc.app.MAX_DOCUMENT_REQUEST_BYTES", 10)
    app.dependency_overrides[get_ocr_engine] = unexpected_ocr_engine
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/ocr",
                content=chunks(),
                headers={
                    "Content-Type": "multipart/form-data; boundary=fixture",
                    "X-Request-ID": "streamed-limit",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "upload_too_large"
    assert response.headers["X-Request-ID"] == "streamed-limit"
    assert dependency_resolved is False
