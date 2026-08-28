"""Proves rejected review requests never resolve processing or storage.

Mirrors test_upload_dependency_order.py's technique (override a dependency
with a sentinel that records whether it ran) but for the review route
family: an actor that fails authentication, CSRF, or origin checks must
never cause the untrusted document to be processed (OCR, extraction, the
reference database) or a review case to be written, no matter how far into
the route's parameter list those dependencies sit.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from veridoc.app import app
from veridoc.processing.dependencies import (
    get_invoice_repository,
    get_processing_service,
)
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


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


@asynccontextmanager
async def _client(tmp_path: Path, *, resolved: list[str]):
    repository = SQLiteReviewRepository(tmp_path / "review.sqlite")
    repository.initialize()

    def _unexpected_processing_service() -> None:
        resolved.append("processing_service")

    def _unexpected_invoice_repository() -> None:
        resolved.append("invoice_repository")

    app.dependency_overrides[get_review_repository] = lambda: repository
    app.dependency_overrides[get_review_actor_directory] = _directory
    app.dependency_overrides[get_review_origin_settings] = lambda: ReviewOriginSettings(
        origin=_ORIGIN
    )
    app.dependency_overrides[get_processing_service] = _unexpected_processing_service
    app.dependency_overrides[get_invoice_repository] = _unexpected_invoice_repository
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client, repository
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_create_case_never_processes_the_document_without_a_session(
    tmp_path: Path,
) -> None:
    resolved: list[str] = []
    async with _client(tmp_path, resolved=resolved) as (client, _repository):
        response = await client.post(
            "/review/cases",
            headers={"Origin": _ORIGIN, IDEMPOTENCY_KEY_HEADER: "case-key-1"},
            files={"file": ("invoice.png", _png_bytes(), "image/png")},
        )

    assert response.status_code == 401
    assert resolved == []


@pytest.mark.anyio
async def test_create_case_never_processes_the_document_with_a_rejected_csrf(
    tmp_path: Path,
) -> None:
    resolved: list[str] = []
    async with _client(tmp_path, resolved=resolved) as (client, _repository):
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
            files={"file": ("invoice.png", _png_bytes(), "image/png")},
        )

    assert response.status_code == 403
    assert resolved == []


@pytest.mark.anyio
async def test_create_case_never_processes_the_document_with_a_mismatched_origin(
    tmp_path: Path,
) -> None:
    resolved: list[str] = []
    async with _client(tmp_path, resolved=resolved) as (client, _repository):
        login = await client.post(
            "/review/session",
            headers={"Authorization": f"Bearer {_REVIEWER_SECRET}", "Origin": _ORIGIN},
        )
        client.cookies.set(
            "veridoc_review_session", login.cookies["veridoc_review_session"]
        )
        client.cookies.set("veridoc_review_csrf", login.cookies["veridoc_review_csrf"])

        response = await client.post(
            "/review/cases",
            headers={
                "Origin": "https://attacker.example",
                CSRF_HEADER_NAME: login.cookies["veridoc_review_csrf"],
                IDEMPOTENCY_KEY_HEADER: "case-key-1",
            },
            files={"file": ("invoice.png", _png_bytes(), "image/png")},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "review_csrf_rejected"
    assert resolved == []


@pytest.mark.anyio
async def test_create_case_never_processes_the_document_for_an_unknown_token(
    tmp_path: Path,
) -> None:
    resolved: list[str] = []
    async with _client(tmp_path, resolved=resolved) as (client, _repository):
        client.cookies.set("veridoc_review_session", "unknown-token")
        client.cookies.set("veridoc_review_csrf", "csrf-token")

        response = await client.post(
            "/review/cases",
            headers={
                "Origin": _ORIGIN,
                CSRF_HEADER_NAME: "csrf-token",
                IDEMPOTENCY_KEY_HEADER: "case-key-1",
            },
            files={"file": ("invoice.png", _png_bytes(), "image/png")},
        )

    assert response.status_code == 401
    assert resolved == []


@pytest.mark.anyio
async def test_assign_case_never_reaches_the_repository_write_without_csrf(
    tmp_path: Path,
) -> None:
    resolved: list[str] = []
    async with _client(tmp_path, resolved=resolved) as (client, repository):
        login = await client.post(
            "/review/session",
            headers={"Authorization": f"Bearer {_REVIEWER_SECRET}", "Origin": _ORIGIN},
        )
        client.cookies.set(
            "veridoc_review_session", login.cookies["veridoc_review_session"]
        )

        response = await client.put(
            "/review/cases/some-case/assignment",
            headers={"Origin": _ORIGIN, IDEMPOTENCY_KEY_HEADER: "assign-key-1"},
            json={"expected_version": 1},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "review_csrf_rejected"
    assert repository.get_case("some-case") is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("method", "path", "request_kwargs"),
    [
        (
            "POST",
            "/review/cases",
            {
                "files": {"file": ("invoice.png", _png_bytes(), "image/png")},
                "headers": {IDEMPOTENCY_KEY_HEADER: "case-key-1"},
            },
        ),
        (
            "PUT",
            "/review/cases/some-case/assignment",
            {
                "json": {"expected_version": 1},
                "headers": {IDEMPOTENCY_KEY_HEADER: "assign-key-1"},
            },
        ),
        (
            "POST",
            "/review/cases/some-case/escalations",
            {
                "json": {"expected_version": 1, "reason": "Needs review."},
                "headers": {IDEMPOTENCY_KEY_HEADER: "escalate-key-1"},
            },
        ),
        (
            "POST",
            "/review/cases/some-case/decisions",
            {
                "json": {
                    "expected_version": 1,
                    "decision": "accept",
                    "reason": "Amounts reconcile.",
                },
                "headers": {IDEMPOTENCY_KEY_HEADER: "decide-key-1"},
            },
        ),
    ],
)
async def test_rejected_csrf_precedes_repository_resolution(
    tmp_path: Path,
    method: str,
    path: str,
    request_kwargs: dict[str, object],
) -> None:
    resolved: list[str] = []
    async with _client(tmp_path, resolved=resolved) as (client, _repository):
        login = await client.post(
            "/review/session",
            headers={"Authorization": f"Bearer {_REVIEWER_SECRET}", "Origin": _ORIGIN},
        )
        client.cookies.set(
            "veridoc_review_session", login.cookies["veridoc_review_session"]
        )

        def _unexpected_review_repository() -> None:
            resolved.append("review_repository")
            raise AssertionError("review repository must not resolve")

        app.dependency_overrides[get_review_repository] = _unexpected_review_repository
        supplied_headers = request_kwargs.pop("headers")
        assert isinstance(supplied_headers, dict)
        response = await client.request(
            method,
            path,
            headers={"Origin": _ORIGIN, **supplied_headers},
            **request_kwargs,
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "review_csrf_rejected"
    assert resolved == []
