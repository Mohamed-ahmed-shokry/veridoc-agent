"""In-process tests for POST /review/cases/{case_id}/escalations."""

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
_REVIEWER_TWO_SECRET = "reviewer-two-secret-value"
_ADMIN_SECRET = "admin-secret-value"
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
            ),
            "reviewer-2": ReviewActor(
                actor_id="reviewer-2",
                role="reviewer",
                secret_digest=_digest(_REVIEWER_TWO_SECRET),
            ),
            "admin-1": ReviewActor(
                actor_id="admin-1",
                role="review_admin",
                secret_digest=_digest(_ADMIN_SECRET),
            ),
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


async def _authenticated_headers(
    client: httpx.AsyncClient, *, secret: str
) -> dict[str, str]:
    login = await client.post(
        "/review/session",
        headers={"Authorization": f"Bearer {secret}", "Origin": _ORIGIN},
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


async def _assign_to_self(
    client: httpx.AsyncClient, headers: dict[str, str], case_id: str
) -> None:
    response = await client.put(
        f"/review/cases/{case_id}/assignment",
        headers={**headers, IDEMPOTENCY_KEY_HEADER: "assign-key-1"},
        json={"expected_version": 1},
    )
    assert response.status_code == 200


async def _escalate(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    case_id: str,
    *,
    expected_version: int,
    reason: str | None = "Amounts do not reconcile.",
    idempotency_key: str = "escalate-key-1",
) -> httpx.Response:
    body: dict[str, object] = {"expected_version": expected_version}
    if reason is not None:
        body["reason"] = reason
    return await client.post(
        f"/review/cases/{case_id}/escalations",
        headers={**headers, IDEMPOTENCY_KEY_HEADER: idempotency_key},
        json=body,
    )


@pytest.mark.anyio
async def test_assignee_escalates_an_assigned_case(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        headers = await _authenticated_headers(client, secret=_REVIEWER_SECRET)
        case_id = await _create_case(client, headers)
        await _assign_to_self(client, headers, case_id)

        response = await _escalate(client, headers, case_id, expected_version=2)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "escalated"
    assert body["version"] == 3
    assert body["events"][-1]["event_type"] == "case_escalated"
    assert body["events"][-1]["reason"] == "Amounts do not reconcile."


@pytest.mark.anyio
async def test_escalate_rejects_a_non_assignee_reviewer(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        owner_headers = await _authenticated_headers(client, secret=_REVIEWER_SECRET)
        case_id = await _create_case(client, owner_headers)
        await _assign_to_self(client, owner_headers, case_id)

        other_headers = await _authenticated_headers(
            client, secret=_REVIEWER_TWO_SECRET
        )
        response = await _escalate(client, other_headers, case_id, expected_version=2)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "review_authorization_denied"


@pytest.mark.anyio
async def test_escalate_rejects_an_unassigned_case(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        headers = await _authenticated_headers(client, secret=_REVIEWER_SECRET)
        case_id = await _create_case(client, headers)

        response = await _escalate(client, headers, case_id, expected_version=1)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "review_authorization_denied"


@pytest.mark.anyio
async def test_escalate_requires_a_reason(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        headers = await _authenticated_headers(client, secret=_REVIEWER_SECRET)
        case_id = await _create_case(client, headers)
        await _assign_to_self(client, headers, case_id)

        response = await _escalate(
            client, headers, case_id, expected_version=2, reason=None
        )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_escalate_returns_404_for_an_unknown_case(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        headers = await _authenticated_headers(client, secret=_REVIEWER_SECRET)

        response = await _escalate(client, headers, "unknown-case", expected_version=1)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "review_case_not_found"


@pytest.mark.anyio
async def test_escalate_is_idempotent_for_a_repeated_key(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        headers = await _authenticated_headers(client, secret=_REVIEWER_SECRET)
        case_id = await _create_case(client, headers)
        await _assign_to_self(client, headers, case_id)

        first = await _escalate(client, headers, case_id, expected_version=2)
        second = await _escalate(client, headers, case_id, expected_version=2)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
