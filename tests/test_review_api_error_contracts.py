"""Cross-route error-contract tests for the review API family.

Each mutating route already has focused coverage of its own auth, CSRF, and
not-found paths in its own test module. This module instead verifies the
contracts that are supposed to hold identically *across* the whole review
route family: generic validation, a genuine idempotency-key conflict,
store-unavailable safety, and request-id correlation on error responses.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException
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


def _png_bytes(*, color: str = "white") -> bytes:
    output = BytesIO()
    Image.new("RGB", (12, 8), color=color).save(output, format="PNG")
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


@pytest.mark.anyio
async def test_create_case_conflicts_on_idempotency_key_reuse_with_new_input(
    tmp_path: Path,
) -> None:
    async with _client(tmp_path) as (client, _repository):
        headers = await _authenticated_headers(client)
        first = await client.post(
            "/review/cases",
            headers={**headers, IDEMPOTENCY_KEY_HEADER: "shared-key"},
            files={"file": ("first.png", _png_bytes(color="white"), "image/png")},
        )
        second = await client.post(
            "/review/cases",
            headers={**headers, IDEMPOTENCY_KEY_HEADER: "shared-key"},
            files={"file": ("second.png", _png_bytes(color="black"), "image/png")},
        )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "review_idempotency_conflict"


@pytest.mark.anyio
async def test_decide_case_rejects_a_malformed_decision_value(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        headers = await _authenticated_headers(client)
        created = await client.post(
            "/review/cases",
            headers={**headers, IDEMPOTENCY_KEY_HEADER: "case-key"},
            files={"file": ("invoice.png", _png_bytes(), "image/png")},
        )
        case_id = created.json()["case_id"]

        response = await client.post(
            f"/review/cases/{case_id}/decisions",
            headers={**headers, IDEMPOTENCY_KEY_HEADER: "decide-key"},
            json={
                "expected_version": 1,
                "decision": "not-a-real-decision",
                "reason": "Testing.",
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_request"


@pytest.mark.anyio
async def test_list_cases_reports_an_unavailable_repository_safely(
    tmp_path: Path,
) -> None:
    async with _client(tmp_path) as (client, _repository):
        headers = await _authenticated_headers(client)

        def _unavailable() -> SQLiteReviewRepository:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "review_data_unavailable",
                    "message": "Review data is not available on this server.",
                },
            )

        app.dependency_overrides[get_review_repository] = _unavailable
        response = await client.get("/review/cases", headers=headers)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "review_data_unavailable"


@pytest.mark.anyio
async def test_review_error_responses_carry_a_correlation_id(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        response = await client.get(
            "/review/cases",
            headers={"Origin": _ORIGIN, "X-Request-ID": "test-correlation-id"},
        )

    assert response.status_code == 401
    assert response.headers["X-Request-ID"] == "test-correlation-id"
