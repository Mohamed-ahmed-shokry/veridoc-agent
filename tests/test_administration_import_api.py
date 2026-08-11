"""In-process tests for bounded authenticated reference-data imports."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from threading import get_ident

import httpx
import pytest

from veridoc.administration.api import get_admin_repository
from veridoc.administration.models import MAX_ADMIN_IMPORT_BYTES
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


def _payload(invoice_number: str = "INV-001") -> dict:
    return {
        "invoices": [
            {
                "metadata": {
                    "source": "fixture",
                    "external_id": "invoice-1",
                },
                "invoice": {
                    "vendor_key": "fictional-supplies",
                    "invoice_number": invoice_number,
                    "total": "42.00",
                },
            }
        ],
        "purchase_orders": [
            {
                "metadata": {
                    "source": "fixture",
                    "external_id": "purchase-order-1",
                },
                "purchase_order": {
                    "vendor_key": "fictional-supplies",
                    "purchase_order_number": "PO-001",
                    "total": "42.00",
                },
            }
        ],
    }


async def _import(
    client: httpx.AsyncClient,
    payload: bytes,
    *,
    query: str = "",
    content_type: str = "application/json",
) -> httpx.Response:
    return await client.post(
        f"/admin/reference-data/import{query}",
        headers=_AUTHORIZATION,
        files={"file": ("reference-data.json", payload, content_type)},
    )


@pytest.mark.anyio
async def test_import_api_supports_dry_run_then_atomic_commit(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _repository(tmp_path)
    monkeypatch.setenv("VERIDOC_ADMIN_TOKEN", _TOKEN)
    payload = json.dumps(_payload()).encode()
    async with _client(repository) as client:
        dry_run = await _import(client, payload, query="?dry_run=true")
        committed = await _import(client, payload)

    assert dry_run.status_code == 200
    assert dry_run.json() == {
        "dry_run": True,
        "created": 2,
        "replaced": 0,
        "skipped": 0,
    }
    assert committed.json()["created"] == 2
    assert repository.list_invoices(vendor_key=None, offset=0, limit=100).total == 1
    assert (
        repository.list_purchase_orders(vendor_key=None, offset=0, limit=100).total == 1
    )


@pytest.mark.anyio
async def test_import_api_runs_storage_work_outside_the_event_loop(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _repository(tmp_path)
    original_import = repository.import_reference_data
    event_loop_thread = get_ident()
    storage_thread: int | None = None

    def observed_import(*args, **kwargs):
        nonlocal storage_thread
        storage_thread = get_ident()
        return original_import(*args, **kwargs)

    monkeypatch.setattr(repository, "import_reference_data", observed_import)
    monkeypatch.setenv("VERIDOC_ADMIN_TOKEN", _TOKEN)
    async with _client(repository) as client:
        response = await _import(client, json.dumps(_payload()).encode())

    assert response.status_code == 200
    assert storage_thread is not None
    assert storage_thread != event_loop_thread


@pytest.mark.anyio
async def test_import_api_exposes_safe_conflict_policy_results(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _repository(tmp_path)
    monkeypatch.setenv("VERIDOC_ADMIN_TOKEN", _TOKEN)
    payload = json.dumps(_payload()).encode()
    async with _client(repository) as client:
        first = await _import(client, payload)
        rejected = await _import(client, payload)
        skipped = await _import(client, payload, query="?conflict=skip")
        replaced = await _import(
            client,
            json.dumps(_payload("INV-REPLACED")).encode(),
            query="?conflict=replace",
        )

    assert first.status_code == 200
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "reference_data_conflict"
    assert skipped.json()["skipped"] == 2
    assert replaced.json()["replaced"] == 2
    invoice = repository.list_invoices(vendor_key=None, offset=0, limit=100).records[0]
    assert invoice.invoice.invoice_number == "INV-REPLACED"


@pytest.mark.anyio
async def test_import_api_rejects_media_type_size_and_malformed_data_safely(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = _repository(tmp_path)
    monkeypatch.setenv("VERIDOC_ADMIN_TOKEN", _TOKEN)
    async with _client(repository) as client:
        wrong_media = await _import(client, b"{}", content_type="text/plain")
        oversized = await _import(client, b"x" * (MAX_ADMIN_IMPORT_BYTES + 1))
        malformed = await _import(client, b'{"invoices":["secret-fragment"')
        invalid = await _import(
            client,
            json.dumps({"invoices": [], "purchase_orders": []}).encode(),
        )

    assert wrong_media.status_code == 415
    assert wrong_media.json()["detail"]["code"] == "unsupported_import_media_type"
    assert oversized.status_code == 413
    assert oversized.json()["detail"]["code"] == "reference_data_import_too_large"
    assert malformed.status_code == 422
    assert malformed.json()["detail"]["code"] == "invalid_reference_data_import"
    assert "secret-fragment" not in malformed.text
    assert invalid.status_code == 422
