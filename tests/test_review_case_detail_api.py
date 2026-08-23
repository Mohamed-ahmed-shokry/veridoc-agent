"""In-process tests for GET /review/cases/{case_id}."""

from __future__ import annotations

from contextlib import asynccontextmanager
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from veridoc.app import app
from veridoc.extraction.models import InvoiceExtraction
from veridoc.processing.dependencies import get_processing_service
from veridoc.processing.models import ProcessingResult, ProcessingVerdict
from veridoc.review.api import (
    CSRF_HEADER_NAME,
    IDEMPOTENCY_KEY_HEADER,
    get_review_actor_directory,
    get_review_origin_settings,
    get_review_repository,
)
from veridoc.review.config import (
    ReviewActor,
    ReviewActorDirectory,
    ReviewOriginSettings,
)
from veridoc.review.persistence.sqlite import SQLiteReviewRepository

_REVIEWER_SECRET = "reviewer-secret-value"
_ORIGIN = "https://review.example"


def _digest(secret: str) -> str:
    return sha256(secret.encode("utf-8")).hexdigest()


def _directory() -> ReviewActorDirectory:
    return ReviewActorDirectory(
        _actors_by_id={
            "reviewer-1": ReviewActor(
                actor_id="reviewer-1",
                role="reviewer",
                secret_digest=_digest(_REVIEWER_SECRET),
            )
        }
    )


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (12, 8), color="white").save(output, format="PNG")
    return output.getvalue()


def _result() -> ProcessingResult:
    return ProcessingResult(
        extraction=InvoiceExtraction(document_type="invoice", invoice_number="INV-001"),
        verdict=ProcessingVerdict(
            status="clear",
            summary="No deterministic verification findings require review.",
            finding_count=0,
        ),
    )


class _FakeProcessingService:
    async def process(self, upload):
        del upload
        return _result()


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


@asynccontextmanager
async def _client(tmp_path: Path):
    repository = SQLiteReviewRepository(tmp_path / "review.sqlite")
    repository.initialize()
    app.dependency_overrides[get_review_repository] = lambda: repository
    app.dependency_overrides[get_review_actor_directory] = _directory
    app.dependency_overrides[get_review_origin_settings] = lambda: ReviewOriginSettings(
        origin=_ORIGIN
    )
    app.dependency_overrides[get_processing_service] = lambda: _FakeProcessingService()
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client, repository
    finally:
        app.dependency_overrides.clear()


async def _authenticated_headers(client: httpx.AsyncClient) -> dict[str, str]:
    login = await client.post(
        "/review/session",
        headers={"Authorization": f"Bearer {_REVIEWER_SECRET}", "Origin": _ORIGIN},
    )
    client.cookies.set(
        "veridoc_review_session", login.cookies["veridoc_review_session"]
    )
    client.cookies.set("veridoc_review_csrf", login.cookies["veridoc_review_csrf"])
    return {
        "Origin": _ORIGIN,
        CSRF_HEADER_NAME: login.cookies["veridoc_review_csrf"],
    }


async def _create_case(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    response = await client.post(
        "/review/cases",
        headers={**headers, IDEMPOTENCY_KEY_HEADER: "case-key-1"},
        files={"file": ("fictional-invoice.png", _png_bytes(), "image/png")},
    )
    assert response.status_code == 201
    return str(response.json()["case_id"])


@pytest.mark.anyio
async def test_read_case_returns_the_snapshot_and_events(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        headers = await _authenticated_headers(client)
        case_id = await _create_case(client, headers)

        response = await client.get(f"/review/cases/{case_id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == case_id
    assert body["snapshot"]["result"]["extraction"]["invoice_number"] == "INV-001"
    assert [event["event_type"] for event in body["events"]] == ["case_created"]


@pytest.mark.anyio
async def test_read_case_returns_404_for_an_unknown_case(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        headers = await _authenticated_headers(client)
        response = await client.get("/review/cases/unknown-case", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "review_case_not_found"


@pytest.mark.anyio
async def test_read_case_requires_authentication(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        response = await client.get(
            "/review/cases/any-case", headers={"Origin": _ORIGIN}
        )

    assert response.status_code == 401
