"""In-process tests for authenticated purchase-order administration routes."""

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


def _payload(*, external_id: str = "purchase-order-1", number: str = "PO-001") -> dict:
    return {
        "metadata": {"source": "fixture", "external_id": external_id},
        "purchase_order": {
            "vendor_key": "fictional-supplies",
            "purchase_order_number": number,
            "currency": "USD",
            "total": "42.00",
        },
    }


@pytest.mark.anyio
async def test_purchase_order_admin_supports_the_complete_record_lifecycle(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _repository(tmp_path)
    monkeypatch.setenv("VERIDOC_ADMIN_TOKEN", _TOKEN)
    async with _client(repository) as client:
        created = await client.post(
            "/admin/reference-data/purchase-orders",
            headers=_AUTHORIZATION,
            json=_payload(),
        )
        record_id = created.json()["metadata"]["record_id"]
        listed = await client.get(
            "/admin/reference-data/purchase-orders",
            headers=_AUTHORIZATION,
            params={"vendor_key": "Fictional Supplies"},
        )
        fetched = await client.get(
            f"/admin/reference-data/purchase-orders/{record_id}",
            headers=_AUTHORIZATION,
        )
        updated = await client.put(
            f"/admin/reference-data/purchase-orders/{record_id}",
            headers=_AUTHORIZATION,
            json={
                "purchase_order": {
                    "vendor_key": "fictional-supplies",
                    "purchase_order_number": "PO-UPDATED",
                },
                "retention_until": "2028-01-01",
            },
        )
        deleted = await client.delete(
            f"/admin/reference-data/purchase-orders/{record_id}",
            headers=_AUTHORIZATION,
        )
        missing = await client.get(
            f"/admin/reference-data/purchase-orders/{record_id}",
            headers=_AUTHORIZATION,
        )

    assert created.status_code == 201
    assert listed.json()["total"] == 1
    assert fetched.json()["purchase_order"]["purchase_order_number"] == "PO-001"
    assert updated.json()["purchase_order"]["purchase_order_number"] == "PO-UPDATED"
    assert updated.json()["metadata"]["retention_until"] == "2028-01-01"
    assert deleted.status_code == 204
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "reference_record_not_found"


@pytest.mark.anyio
async def test_purchase_order_admin_returns_safe_conflict_and_validation_errors(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _repository(tmp_path)
    monkeypatch.setenv("VERIDOC_ADMIN_TOKEN", _TOKEN)
    async with _client(repository) as client:
        first = await client.post(
            "/admin/reference-data/purchase-orders",
            headers=_AUTHORIZATION,
            json=_payload(),
        )
        natural_conflict = await client.post(
            "/admin/reference-data/purchase-orders",
            headers=_AUTHORIZATION,
            json=_payload(external_id="purchase-order-2"),
        )
        provenance_conflict = await client.post(
            "/admin/reference-data/purchase-orders",
            headers=_AUTHORIZATION,
            json=_payload(number="PO-002"),
        )
        invalid = await client.post(
            "/admin/reference-data/purchase-orders",
            headers=_AUTHORIZATION,
            json={**_payload(external_id="unsafe id"), "document_body": "secret"},
        )

    assert first.status_code == 201
    assert natural_conflict.status_code == 409
    assert provenance_conflict.status_code == 409
    assert natural_conflict.json()["detail"]["code"] == "reference_data_conflict"
    assert invalid.status_code == 422
