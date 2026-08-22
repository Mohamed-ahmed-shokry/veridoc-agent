"""In-process tests for the review browser-session creation endpoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from hashlib import sha256
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException

from veridoc.app import app
from veridoc.review.api import (
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


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


@asynccontextmanager
async def _client(
    tmp_path: Path,
    *,
    origin_available: bool = True,
    directory: ReviewActorDirectory | None = None,
):
    repository = SQLiteReviewRepository(tmp_path / "review.sqlite")
    repository.initialize()
    app.dependency_overrides[get_review_repository] = lambda: repository
    app.dependency_overrides[get_review_actor_directory] = lambda: (
        directory or _directory()
    )
    if origin_available:
        app.dependency_overrides[get_review_origin_settings] = lambda: (
            ReviewOriginSettings(origin="https://review.example")
        )
    else:

        def _unavailable() -> ReviewOriginSettings:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "review_authentication_unavailable",
                    "message": "Review authentication is not available on this server.",
                },
            )

        app.dependency_overrides[get_review_origin_settings] = _unavailable
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client, repository
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_create_session_sets_a_secure_httponly_cookie(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        response = await client.post(
            "/review/session",
            headers={"Authorization": f"Bearer {_REVIEWER_SECRET}"},
        )

    assert response.status_code == 201
    assert response.json() == {"actor_id": "reviewer-1", "role": "reviewer"}
    set_cookie = response.headers.get("set-cookie", "")
    assert "veridoc_review_session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "SameSite=strict" in set_cookie.lower().replace("samesite", "SameSite")
    assert "Path=/review" in set_cookie


@pytest.mark.anyio
async def test_create_session_never_returns_the_raw_token_in_the_body(
    tmp_path: Path,
) -> None:
    async with _client(tmp_path) as (client, _repository):
        response = await client.post(
            "/review/session",
            headers={"Authorization": f"Bearer {_REVIEWER_SECRET}"},
        )

    assert _REVIEWER_SECRET not in response.text
    cookie_value = response.cookies["veridoc_review_session"]
    assert cookie_value not in response.text


@pytest.mark.anyio
async def test_create_session_rejects_missing_credentials_generically(
    tmp_path: Path,
) -> None:
    async with _client(tmp_path) as (client, _repository):
        response = await client.post("/review/session")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_review_credentials"


@pytest.mark.anyio
async def test_create_session_rejects_wrong_credentials_generically(
    tmp_path: Path,
) -> None:
    async with _client(tmp_path) as (client, _repository):
        response = await client.post(
            "/review/session",
            headers={"Authorization": "Bearer wrong-secret"},
        )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_review_credentials"


@pytest.mark.anyio
async def test_create_session_reports_unavailable_origin_configuration(
    tmp_path: Path,
) -> None:
    async with _client(tmp_path, origin_available=False) as (client, _repository):
        response = await client.post(
            "/review/session",
            headers={"Authorization": f"Bearer {_REVIEWER_SECRET}"},
        )

    assert response.status_code == 503


@pytest.mark.anyio
async def test_create_session_persists_a_resolvable_session(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, repository):
        response = await client.post(
            "/review/session",
            headers={"Authorization": f"Bearer {_REVIEWER_SECRET}"},
        )

    cookie_value = response.cookies["veridoc_review_session"]
    resolved = repository.resolve_session(sha256(cookie_value.encode()).hexdigest())
    assert resolved is not None
    assert resolved.actor_id == "reviewer-1"
