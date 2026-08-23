"""In-process tests for GET /review/cases."""

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
from veridoc.review.models import CaseAssignmentRequest
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


async def _create_case(
    client: httpx.AsyncClient, headers: dict[str, str], *, idempotency_key: str
) -> str:
    response = await client.post(
        "/review/cases",
        headers={**headers, IDEMPOTENCY_KEY_HEADER: idempotency_key},
        files={"file": ("fictional-invoice.png", _png_bytes(), "image/png")},
    )
    assert response.status_code == 201
    return str(response.json()["case_id"])


@pytest.mark.anyio
async def test_list_cases_returns_a_bounded_page(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        headers = await _authenticated_headers(client)
        for index in range(3):
            await _create_case(client, headers, idempotency_key=f"case-{index}")

        response = await client.get(
            "/review/cases", headers=headers, params={"limit": 2}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert len(body["records"]) == 2
    assert "snapshot" not in body["records"][0]


@pytest.mark.anyio
async def test_list_cases_filters_by_status_and_assignee(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, repository):
        headers = await _authenticated_headers(client)
        unassigned_id = await _create_case(
            client, headers, idempotency_key="unassigned"
        )
        assigned_id = await _create_case(client, headers, idempotency_key="assigned")
        repository.assign_case(
            assigned_id,
            request=CaseAssignmentRequest(expected_version=1, actor_id="reviewer-1"),
            actor_id="reviewer-1",
            actor_role="reviewer",
            request_id="req-assign-1",
            idempotent_request=None,
        )

        assigned_response = await client.get(
            "/review/cases",
            headers=headers,
            params={"status": "assigned", "assignee_id": "reviewer-1"},
        )
        unassigned_response = await client.get(
            "/review/cases", headers=headers, params={"status": "unassigned"}
        )

    assert [record["case_id"] for record in assigned_response.json()["records"]] == [
        assigned_id
    ]
    assert [record["case_id"] for record in unassigned_response.json()["records"]] == [
        unassigned_id
    ]


@pytest.mark.anyio
async def test_list_cases_requires_authentication(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        response = await client.get("/review/cases", headers={"Origin": _ORIGIN})

    assert response.status_code == 401


@pytest.mark.anyio
async def test_list_cases_rejects_an_out_of_range_limit(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        headers = await _authenticated_headers(client)
        response = await client.get(
            "/review/cases", headers=headers, params={"limit": 500}
        )

    assert response.status_code == 422
