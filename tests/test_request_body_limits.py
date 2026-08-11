"""Pre-parser request-body limit tests."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI

from veridoc.administration.api import require_admin
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


@pytest.mark.anyio
async def test_mounted_document_limit_uses_the_route_relative_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dependency_resolved = False

    def unexpected_ocr_engine() -> None:
        nonlocal dependency_resolved
        dependency_resolved = True

    monkeypatch.setattr("veridoc.app.MAX_DOCUMENT_REQUEST_BYTES", 10)
    app.dependency_overrides[get_ocr_engine] = unexpected_ocr_engine
    mounted_app = FastAPI()
    mounted_app.mount("/api", app)
    transport = httpx.ASGITransport(app=mounted_app)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/ocr",
                content=b"",
                headers={
                    "Content-Length": "11",
                    "Content-Type": "multipart/form-data; boundary=fixture",
                    "X-Request-ID": "mounted-document-limit",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "upload_too_large"
    assert response.headers["X-Request-ID"] == "mounted-document-limit"
    assert dependency_resolved is False


@pytest.mark.anyio
async def test_mounted_import_limit_counts_streamed_body_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dependency_resolved = False

    def unexpected_authentication() -> None:
        nonlocal dependency_resolved
        dependency_resolved = True

    async def chunks() -> AsyncIterator[bytes]:
        yield b"a" * 6
        yield b"b" * 5

    monkeypatch.setattr("veridoc.app.MAX_ADMIN_IMPORT_REQUEST_BYTES", 10)
    app.dependency_overrides[require_admin] = unexpected_authentication
    mounted_app = FastAPI()
    mounted_app.mount("/api", app)
    transport = httpx.ASGITransport(app=mounted_app)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/admin/reference-data/import",
                content=chunks(),
                headers={
                    "Content-Type": "multipart/form-data; boundary=fixture",
                    "X-Request-ID": "mounted-import-limit",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "reference_data_import_too_large"
    assert response.headers["X-Request-ID"] == "mounted-import-limit"
    assert dependency_resolved is False


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/admin/reference-data/invoices"),
        ("PUT", "/admin/reference-data/invoices/record-1"),
        ("POST", "/admin/reference-data/purchase-orders"),
        ("PUT", "/admin/reference-data/purchase-orders/record-1"),
    ],
)
async def test_declared_oversized_admin_json_is_rejected_before_authentication(
    method: str,
    path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authentication_resolved = False

    def unexpected_authentication() -> None:
        nonlocal authentication_resolved
        authentication_resolved = True

    monkeypatch.setattr("veridoc.app.MAX_ADMIN_JSON_REQUEST_BYTES", 10)
    app.dependency_overrides[require_admin] = unexpected_authentication
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.request(
                method,
                path,
                content=b"",
                headers={
                    "Content-Length": "11",
                    "Content-Type": "application/json",
                    "X-Request-ID": "admin-json-limit",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "reference_data_request_too_large"
    assert response.headers["X-Request-ID"] == "admin-json-limit"
    assert authentication_resolved is False


@pytest.mark.anyio
async def test_streamed_oversized_admin_json_is_rejected_before_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authentication_resolved = False

    def unexpected_authentication() -> None:
        nonlocal authentication_resolved
        authentication_resolved = True

    async def chunks() -> AsyncIterator[bytes]:
        yield b"a" * 6
        yield b"b" * 5

    monkeypatch.setattr("veridoc.app.MAX_ADMIN_JSON_REQUEST_BYTES", 10)
    app.dependency_overrides[require_admin] = unexpected_authentication
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/admin/reference-data/invoices",
                content=chunks(),
                headers={
                    "Content-Type": "application/json",
                    "X-Request-ID": "streamed-admin-json-limit",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "reference_data_request_too_large"
    assert response.headers["X-Request-ID"] == "streamed-admin-json-limit"
    assert authentication_resolved is False
