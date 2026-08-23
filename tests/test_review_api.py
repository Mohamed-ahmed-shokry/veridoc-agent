"""Tests for the review-actor session authentication dependency."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import httpx
import pytest
from fastapi import Depends, FastAPI, HTTPException

from veridoc.review.api import (
    SESSION_COOKIE_NAME,
    AuthenticatedActor,
    get_review_actor_directory,
    get_review_origin_settings,
    get_review_repository,
    require_review_actor,
)
from veridoc.review.auth import issue_session
from veridoc.review.config import (
    ReviewActor,
    ReviewActorDirectory,
    ReviewOriginSettings,
)
from veridoc.review.models import ReviewSession


def _now() -> datetime:
    """Compute the reference instant at call time.

    A hardcoded calendar date would eventually fall behind real wall-clock
    time (which is what ``require_review_actor`` actually compares against),
    silently turning an "active session" fixture into an expired one.
    """
    return datetime.now(UTC)


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


class _FakeSessionStore:
    def __init__(self, sessions: dict[str, ReviewSession]) -> None:
        self._sessions = sessions

    def resolve_session(self, session_digest: str) -> ReviewSession | None:
        return self._sessions.get(session_digest)


def _directory() -> ReviewActorDirectory:
    return ReviewActorDirectory(
        _actors_by_id={
            "reviewer-1": ReviewActor(
                actor_id="reviewer-1", role="reviewer", secret_digest="a" * 64
            )
        }
    )


def _test_app(
    *,
    sessions: dict[str, ReviewSession] | None = None,
    directory: ReviewActorDirectory | None = None,
    origin_available: bool = True,
) -> FastAPI:
    test_app = FastAPI()

    @test_app.get("/protected")
    def protected(
        actor: Annotated[AuthenticatedActor, Depends(require_review_actor)],
    ) -> dict[str, str]:
        return {"actor_id": actor.actor_id, "role": actor.role}

    test_app.dependency_overrides[get_review_repository] = lambda: _FakeSessionStore(
        sessions or {}
    )
    test_app.dependency_overrides[get_review_actor_directory] = lambda: (
        directory or _directory()
    )

    def _origin() -> ReviewOriginSettings:
        if not origin_available:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "review_authentication_unavailable",
                    "message": "Review authentication is not available on this server.",
                },
            )
        return ReviewOriginSettings(origin="https://review.example")

    test_app.dependency_overrides[get_review_origin_settings] = _origin
    return test_app


async def _get(test_app: FastAPI, *, cookie: str | None) -> httpx.Response:
    transport = httpx.ASGITransport(app=test_app)
    cookies = {SESSION_COOKIE_NAME: cookie} if cookie is not None else {}
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", cookies=cookies
    ) as client:
        return await client.get("/protected")


@pytest.mark.anyio
async def test_require_review_actor_accepts_a_valid_active_session() -> None:
    now = _now()
    issued = issue_session(now=now)
    session = ReviewSession(
        session_digest=issued.digest,
        actor_id="reviewer-1",
        created_at=now,
        expires_at=issued.expires_at,
    )
    test_app = _test_app(sessions={issued.digest: session})

    response = await _get(test_app, cookie=issued.token)

    assert response.status_code == 200
    assert response.json() == {"actor_id": "reviewer-1", "role": "reviewer"}


@pytest.mark.anyio
async def test_require_review_actor_rejects_a_missing_cookie() -> None:
    test_app = _test_app()

    response = await _get(test_app, cookie=None)

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_review_session"


@pytest.mark.anyio
async def test_require_review_actor_rejects_an_unknown_token() -> None:
    test_app = _test_app()

    response = await _get(test_app, cookie="unknown-token")

    assert response.status_code == 401


@pytest.mark.anyio
async def test_require_review_actor_rejects_an_expired_session() -> None:
    now = _now()
    issued = issue_session(now=now)
    session = ReviewSession(
        session_digest=issued.digest,
        actor_id="reviewer-1",
        created_at=now - timedelta(hours=13),
        expires_at=now - timedelta(hours=1),
    )
    test_app = _test_app(sessions={issued.digest: session})

    response = await _get(test_app, cookie=issued.token)

    assert response.status_code == 401


@pytest.mark.anyio
async def test_require_review_actor_rejects_a_revoked_session() -> None:
    now = _now()
    issued = issue_session(now=now)
    session = ReviewSession(
        session_digest=issued.digest,
        actor_id="reviewer-1",
        created_at=now,
        expires_at=issued.expires_at,
        revoked_at=now,
    )
    test_app = _test_app(sessions={issued.digest: session})

    response = await _get(test_app, cookie=issued.token)

    assert response.status_code == 401


@pytest.mark.anyio
async def test_require_review_actor_rejects_a_session_for_a_removed_actor() -> None:
    now = _now()
    issued = issue_session(now=now)
    session = ReviewSession(
        session_digest=issued.digest,
        actor_id="reviewer-removed",
        created_at=now,
        expires_at=issued.expires_at,
    )
    test_app = _test_app(sessions={issued.digest: session})

    response = await _get(test_app, cookie=issued.token)

    assert response.status_code == 401


@pytest.mark.anyio
async def test_require_review_actor_reports_unavailable_origin_configuration() -> None:
    test_app = _test_app(origin_available=False)

    response = await _get(test_app, cookie="any-token")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "review_authentication_unavailable"
