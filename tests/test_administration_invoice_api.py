"""In-process tests for authenticated invoice administration routes."""

from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import pytest

from veridoc.administration.api import get_admin_repository
from veridoc.app import app
from veridoc.persistence.sqlite import SQLiteInvoiceRepository

_TOKEN = "phase-8-fixture-token-000000000000"
_AUTHORIZATION = {"Authorization": f"Bearer {_TOKEN}"}


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


def _repository(tmp_path) -> SQLiteInvoiceRepository:
    repository = SQLiteInvoiceRepository(tmp_path / "reference-data.sqlite")
    repository.initialize()
    return repository


@asynccontextmanager
async def _client(repository: SQLiteInvoiceRepository):
    app.dependency_overrides[get_admin_repository] = lambda: repository
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def _payload(
    *, external_id: str = "invoice-1", invoice_number: str = "INV-001"
) -> dict:
    return {
        "metadata": {"source": "fixture", "external_id": external_id},
        "invoice": {
            "vendor_key": "fictional-supplies",
            "invoice_number": invoice_number,
            "currency": "USD",
            "total": "42.00",
        },
    }


def test_admin_routes_publish_the_bearer_security_contract() -> None:
    schema = app.openapi()

    assert schema["components"]["securitySchemes"]["AdminBearer"] == {
        "type": "http",
        "description": "Local reference-data administration token.",
        "scheme": "bearer",
    }
    for path, operations in schema["paths"].items():
        for operation in operations.values():
            if path.startswith("/admin/reference-data/"):
                assert operation["security"] == [{"AdminBearer": []}]
    assert "security" not in schema["paths"]["/health"]["get"]


@pytest.mark.anyio
async def test_admin_authentication_precedes_repository_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_resolved = False

    def resolve_repository() -> None:
        nonlocal repository_resolved
        repository_resolved = True
        raise AssertionError("unauthenticated requests must not resolve storage")

    monkeypatch.delenv("VERIDOC_ADMIN_TOKEN", raising=False)
    app.dependency_overrides[get_admin_repository] = resolve_repository
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/admin/reference-data/invoices",
                headers=_AUTHORIZATION,
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert repository_resolved is False


@pytest.mark.anyio
async def test_invoice_admin_requires_configured_valid_bearer_token(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _repository(tmp_path)
    monkeypatch.delenv("VERIDOC_ADMIN_TOKEN", raising=False)
    async with _client(repository) as client:
        unavailable = await client.get(
            "/admin/reference-data/invoices",
            headers=_AUTHORIZATION,
        )

    monkeypatch.setenv("VERIDOC_ADMIN_TOKEN", _TOKEN)
    async with _client(repository) as client:
        missing = await client.get("/admin/reference-data/invoices")
        incorrect = await client.get(
            "/admin/reference-data/invoices",
            headers={"Authorization": "Bearer incorrect"},
        )

    assert unavailable.status_code == 503
    assert unavailable.json()["detail"]["code"] == "admin_authentication_unavailable"
    assert missing.status_code == 401
    assert missing.headers["WWW-Authenticate"] == "Bearer"
    assert incorrect.status_code == 401
    assert incorrect.json()["detail"]["code"] == "invalid_admin_credentials"


@pytest.mark.anyio
async def test_invoice_admin_supports_the_complete_record_lifecycle(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _repository(tmp_path)
    monkeypatch.setenv("VERIDOC_ADMIN_TOKEN", _TOKEN)
    async with _client(repository) as client:
        created = await client.post(
            "/admin/reference-data/invoices",
            headers=_AUTHORIZATION,
            json=_payload(),
        )
        record_id = created.json()["metadata"]["record_id"]
        listed = await client.get(
            "/admin/reference-data/invoices?vendor_key=fictional-supplies",
            headers=_AUTHORIZATION,
        )
        fetched = await client.get(
            f"/admin/reference-data/invoices/{record_id}",
            headers=_AUTHORIZATION,
        )
        updated = await client.put(
            f"/admin/reference-data/invoices/{record_id}",
            headers=_AUTHORIZATION,
            json={
                "invoice": {
                    "vendor_key": "fictional-supplies",
                    "invoice_number": "INV-UPDATED",
                },
                "retention_until": "2028-01-01",
            },
        )
        deleted = await client.delete(
            f"/admin/reference-data/invoices/{record_id}",
            headers=_AUTHORIZATION,
        )
        missing = await client.get(
            f"/admin/reference-data/invoices/{record_id}",
            headers=_AUTHORIZATION,
        )

    assert created.status_code == 201
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert fetched.json()["invoice"]["invoice_number"] == "INV-001"
    assert updated.json()["invoice"]["invoice_number"] == "INV-UPDATED"
    assert updated.json()["metadata"]["retention_until"] == "2028-01-01"
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "reference_record_not_found"


@pytest.mark.anyio
async def test_invoice_admin_returns_safe_conflict_and_validation_errors(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _repository(tmp_path)
    monkeypatch.setenv("VERIDOC_ADMIN_TOKEN", _TOKEN)
    async with _client(repository) as client:
        first = await client.post(
            "/admin/reference-data/invoices",
            headers=_AUTHORIZATION,
            json=_payload(),
        )
        conflict = await client.post(
            "/admin/reference-data/invoices",
            headers=_AUTHORIZATION,
            json=_payload(invoice_number="INV-002"),
        )
        invalid = await client.post(
            "/admin/reference-data/invoices",
            headers=_AUTHORIZATION,
            json={**_payload(external_id="unsafe id"), "document_body": "secret"},
        )
        invalid_page = await client.get(
            "/admin/reference-data/invoices?limit=201",
            headers=_AUTHORIZATION,
        )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "reference_data_conflict"
    assert invalid.status_code == 422
    assert invalid_page.status_code == 422
