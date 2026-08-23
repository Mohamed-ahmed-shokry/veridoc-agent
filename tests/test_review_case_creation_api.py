"""In-process tests for POST /review/cases."""

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
from veridoc.ocr.protocol import OCRProcessingError, OCRUnavailableError
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
    def __init__(self, *, error: Exception | None = None) -> None:
        self.uploads = []
        self._error = error

    async def process(self, upload):
        self.uploads.append(upload)
        if self._error is not None:
            raise self._error
        return _result()


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


@asynccontextmanager
async def _client(
    tmp_path: Path,
    *,
    service: _FakeProcessingService | None = None,
):
    repository = SQLiteReviewRepository(tmp_path / "review.sqlite")
    repository.initialize()
    app.dependency_overrides[get_review_repository] = lambda: repository
    app.dependency_overrides[get_review_actor_directory] = _directory
    app.dependency_overrides[get_review_origin_settings] = lambda: ReviewOriginSettings(
        origin=_ORIGIN
    )
    app.dependency_overrides[get_processing_service] = lambda: (
        service or _FakeProcessingService()
    )
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


async def _post_case(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    idempotency_key: str = "case-key-1",
) -> httpx.Response:
    return await client.post(
        "/review/cases",
        headers={**headers, IDEMPOTENCY_KEY_HEADER: idempotency_key},
        files={"file": ("fictional-invoice.png", _png_bytes(), "image/png")},
    )


@pytest.mark.anyio
async def test_create_case_returns_the_typed_snapshot_and_initial_event(
    tmp_path: Path,
) -> None:
    service = _FakeProcessingService()
    async with _client(tmp_path, service=service) as (client, _repository):
        headers = await _authenticated_headers(client)
        response = await _post_case(client, headers)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "unassigned"
    assert body["version"] == 1
    assert body["creator_actor_id"] == "reviewer-1"
    assert body["snapshot"]["result"]["extraction"]["invoice_number"] == "INV-001"
    assert [event["event_type"] for event in body["events"]] == ["case_created"]
    assert service.uploads[0].filename == "fictional-invoice.png"


@pytest.mark.anyio
async def test_create_case_requires_authentication(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        response = await client.post(
            "/review/cases",
            headers={"Origin": _ORIGIN, IDEMPOTENCY_KEY_HEADER: "case-key-1"},
            files={"file": ("fictional-invoice.png", _png_bytes(), "image/png")},
        )

    assert response.status_code == 401


@pytest.mark.anyio
async def test_create_case_requires_csrf_protection(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        login = await client.post(
            "/review/session",
            headers={"Authorization": f"Bearer {_REVIEWER_SECRET}", "Origin": _ORIGIN},
        )
        client.cookies.set(
            "veridoc_review_session", login.cookies["veridoc_review_session"]
        )
        response = await client.post(
            "/review/cases",
            headers={"Origin": _ORIGIN, IDEMPOTENCY_KEY_HEADER: "case-key-1"},
            files={"file": ("fictional-invoice.png", _png_bytes(), "image/png")},
        )

    assert response.status_code == 403


@pytest.mark.anyio
async def test_create_case_requires_an_idempotency_key(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        headers = await _authenticated_headers(client)
        response = await client.post(
            "/review/cases",
            headers=headers,
            files={"file": ("fictional-invoice.png", _png_bytes(), "image/png")},
        )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "missing_idempotency_key"


@pytest.mark.anyio
async def test_create_case_is_idempotent_for_a_repeated_key(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        headers = await _authenticated_headers(client)
        first = await _post_case(client, headers)
        second = await _post_case(client, headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["case_id"] == second.json()["case_id"]


@pytest.mark.anyio
async def test_create_case_reports_unavailable_ocr_safely(tmp_path: Path) -> None:
    service = _FakeProcessingService(error=OCRUnavailableError())
    async with _client(tmp_path, service=service) as (client, _repository):
        headers = await _authenticated_headers(client)
        response = await _post_case(client, headers)

    assert response.status_code == 503


@pytest.mark.anyio
async def test_create_case_reports_ocr_processing_failure_safely(
    tmp_path: Path,
) -> None:
    service = _FakeProcessingService(error=OCRProcessingError())
    async with _client(tmp_path, service=service) as (client, _repository):
        headers = await _authenticated_headers(client)
        response = await _post_case(client, headers)

    assert response.status_code == 422
