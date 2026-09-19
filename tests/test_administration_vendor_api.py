"""In-process tests for authenticated vendor administration routes."""

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
    *,
    external_id: str = "vendor-1",
    vendor_id: str = "vnd_001",
    status: str = "active",
) -> dict:
    return {
        "metadata": {"source": "fixture", "external_id": external_id},
        "vendor": {
            "vendor_id": vendor_id,
            "legal_name": "Acme Supplies Corp",
            "canonical_key": "acme-supplies",
            "status": status,
            "aliases": ["Acme Supplies"],
            "bank_accounts": [
                {
                    "account_number": "12345678",
                    "iban": "GB29NWBK60161331926819",
                }
            ],
            "tax_ids": [
                {
                    "tax_id": "GB123456789",
                    "tax_type": "VAT",
                    "country_code": "GB",
                }
            ],
        },
    }


@pytest.mark.anyio
async def test_vendor_admin_crud_lifecycle(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VERIDOC_ADMIN_TOKEN", _TOKEN)
    repository = _repository(tmp_path)

    async with _client(repository) as client:
        # Create vendor
        create_resp = await client.post(
            "/admin/reference-data/vendors",
            json=_payload(),
            headers=_AUTHORIZATION,
        )
        assert create_resp.status_code == 201
        created = create_resp.json()
        assert created["vendor"]["vendor_id"] == "vnd_001"
        assert created["vendor"]["legal_name"] == "Acme Supplies Corp"
        assert created["vendor"]["canonical_key"] == "acme-supplies"
        record_id = created["metadata"]["record_id"]

        # Conflict on duplicate vendor_id
        dup_resp = await client.post(
            "/admin/reference-data/vendors",
            json=_payload(external_id="vendor-2", vendor_id="vnd_001"),
            headers=_AUTHORIZATION,
        )
        assert dup_resp.status_code == 409
        assert dup_resp.json()["detail"]["code"] == "reference_data_conflict"

        # Fetch vendor by record_id
        get_resp = await client.get(
            f"/admin/reference-data/vendors/{record_id}",
            headers=_AUTHORIZATION,
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["metadata"]["record_id"] == record_id

        # List vendors
        list_resp = await client.get(
            "/admin/reference-data/vendors",
            headers=_AUTHORIZATION,
        )
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] == 1
        assert len(list_resp.json()["records"]) == 1

        # List with status filter
        filter_resp = await client.get(
            "/admin/reference-data/vendors?status=suspended",
            headers=_AUTHORIZATION,
        )
        assert filter_resp.status_code == 200
        assert filter_resp.json()["total"] == 0

        # Update vendor
        update_payload = {
            "vendor": {
                "vendor_id": "vnd_001",
                "legal_name": "Acme Supplies International Ltd",
                "canonical_key": "acme-supplies",
                "status": "suspended",
                "aliases": ["Acme Int"],
                "bank_accounts": [],
                "tax_ids": [],
            }
        }
        update_resp = await client.put(
            f"/admin/reference-data/vendors/{record_id}",
            json=update_payload,
            headers=_AUTHORIZATION,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["vendor"]["status"] == "suspended"
        assert (
            update_resp.json()["vendor"]["legal_name"]
            == "Acme Supplies International Ltd"
        )

        # Delete vendor
        del_resp = await client.delete(
            f"/admin/reference-data/vendors/{record_id}",
            headers=_AUTHORIZATION,
        )
        assert del_resp.status_code == 204

        # 404 after deletion
        get_after_del = await client.get(
            f"/admin/reference-data/vendors/{record_id}",
            headers=_AUTHORIZATION,
        )
        assert get_after_del.status_code == 404


@pytest.mark.anyio
async def test_vendor_admin_rejects_missing_or_invalid_auth(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("VERIDOC_ADMIN_TOKEN", _TOKEN)
    repository = _repository(tmp_path)

    async with _client(repository) as client:
        # Missing auth header
        resp = await client.get("/admin/reference-data/vendors")
        assert resp.status_code == 401

        # Wrong token
        resp = await client.get(
            "/admin/reference-data/vendors",
            headers={"Authorization": "Bearer wrong-token-00000000000000"},
        )
        assert resp.status_code == 401


@pytest.mark.anyio
async def test_vendor_admin_returns_404_for_unknown_record(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("VERIDOC_ADMIN_TOKEN", _TOKEN)
    repository = _repository(tmp_path)

    async with _client(repository) as client:
        resp = await client.get(
            "/admin/reference-data/vendors/nonexistent",
            headers=_AUTHORIZATION,
        )
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "reference_record_not_found"

        del_resp = await client.delete(
            "/admin/reference-data/vendors/nonexistent",
            headers=_AUTHORIZATION,
        )
        assert del_resp.status_code == 404
