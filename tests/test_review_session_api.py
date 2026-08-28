"""In-process tests for the review browser-session creation and CSRF protection."""

from __future__ import annotations

from contextlib import asynccontextmanager
from hashlib import sha256
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException

from veridoc.app import app
from veridoc.review.api import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
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
            ReviewOriginSettings(origin=_ORIGIN)
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


async def _login(client: httpx.AsyncClient) -> httpx.Response:
    return await client.post(
        "/review/session",
        headers={"Authorization": f"Bearer {_REVIEWER_SECRET}", "Origin": _ORIGIN},
    )


def _attach_session_cookies(client: httpx.AsyncClient, login: httpx.Response) -> None:
    # httpx's cookie jar correctly refuses to resend Secure cookies over this
    # test transport's plain http:// base_url, mirroring real browser
    # behavior, so both cookies must be attached explicitly for later requests.
    client.cookies.set(SESSION_COOKIE_NAME, login.cookies[SESSION_COOKIE_NAME])
    client.cookies.set(CSRF_COOKIE_NAME, login.cookies[CSRF_COOKIE_NAME])


@pytest.mark.anyio
async def test_create_session_sets_secure_cookies(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        response = await _login(client)

    assert response.status_code == 201
    assert response.json() == {"actor_id": "reviewer-1", "role": "reviewer"}
    set_cookie_headers = response.headers.get_list("set-cookie")
    session_cookie = next(
        c for c in set_cookie_headers if c.startswith(SESSION_COOKIE_NAME)
    )
    csrf_cookie = next(c for c in set_cookie_headers if c.startswith(CSRF_COOKIE_NAME))

    assert "HttpOnly" in session_cookie
    assert "Secure" in session_cookie
    assert "Path=/review" in session_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "Secure" in csrf_cookie
    assert "Path=/review" in csrf_cookie


@pytest.mark.anyio
async def test_create_session_never_returns_the_raw_token_in_the_body(
    tmp_path: Path,
) -> None:
    async with _client(tmp_path) as (client, _repository):
        response = await _login(client)

    assert _REVIEWER_SECRET not in response.text
    assert response.cookies[SESSION_COOKIE_NAME] not in response.text


@pytest.mark.anyio
async def test_create_session_rejects_missing_credentials_generically(
    tmp_path: Path,
) -> None:
    async with _client(tmp_path) as (client, _repository):
        response = await client.post("/review/session", headers={"Origin": _ORIGIN})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_review_credentials"


@pytest.mark.anyio
async def test_create_session_rejects_wrong_credentials_generically(
    tmp_path: Path,
) -> None:
    async with _client(tmp_path) as (client, _repository):
        response = await client.post(
            "/review/session",
            headers={"Authorization": "Bearer wrong-secret", "Origin": _ORIGIN},
        )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_review_credentials"


@pytest.mark.anyio
async def test_invalid_login_is_rejected_before_repository_resolution() -> None:
    repository_resolved = False

    def _unexpected_repository() -> None:
        nonlocal repository_resolved
        repository_resolved = True
        raise AssertionError("review repository must not resolve")

    app.dependency_overrides[get_review_origin_settings] = lambda: ReviewOriginSettings(
        origin=_ORIGIN
    )
    app.dependency_overrides[get_review_actor_directory] = _directory
    app.dependency_overrides[get_review_repository] = _unexpected_repository
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/review/session",
                headers={"Authorization": "Bearer wrong-secret", "Origin": _ORIGIN},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_review_credentials"
    assert repository_resolved is False


@pytest.mark.anyio
async def test_create_session_reports_unavailable_origin_configuration(
    tmp_path: Path,
) -> None:
    async with _client(tmp_path, origin_available=False) as (client, _repository):
        response = await client.post(
            "/review/session",
            headers={"Authorization": f"Bearer {_REVIEWER_SECRET}", "Origin": _ORIGIN},
        )

    assert response.status_code == 503


@pytest.mark.anyio
async def test_create_session_rejects_a_mismatched_origin(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        response = await client.post(
            "/review/session",
            headers={
                "Authorization": f"Bearer {_REVIEWER_SECRET}",
                "Origin": "https://attacker.example",
            },
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "review_csrf_rejected"


@pytest.mark.anyio
async def test_create_session_rejects_a_missing_origin_header(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        response = await client.post(
            "/review/session",
            headers={"Authorization": f"Bearer {_REVIEWER_SECRET}"},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "review_csrf_rejected"


@pytest.mark.anyio
async def test_create_session_persists_a_resolvable_session(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, repository):
        response = await _login(client)

    resolved = repository.resolve_session(
        sha256(response.cookies[SESSION_COOKIE_NAME].encode()).hexdigest()
    )
    assert resolved is not None
    assert resolved.actor_id == "reviewer-1"


@pytest.mark.anyio
async def test_revoke_session_clears_the_cookies_and_the_stored_session(
    tmp_path: Path,
) -> None:
    async with _client(tmp_path) as (client, repository):
        login = await _login(client)
        digest = sha256(login.cookies[SESSION_COOKIE_NAME].encode()).hexdigest()
        _attach_session_cookies(client, login)

        response = await client.delete(
            "/review/session",
            headers={
                "Origin": _ORIGIN,
                CSRF_HEADER_NAME: login.cookies[CSRF_COOKIE_NAME],
            },
        )

    assert response.status_code == 204
    revoked = repository.resolve_session(digest)
    assert revoked is not None
    assert revoked.revoked_at is not None
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any(c.startswith(f'{SESSION_COOKIE_NAME}=""') for c in set_cookie_headers)
    assert any(c.startswith(f'{CSRF_COOKIE_NAME}=""') for c in set_cookie_headers)


@pytest.mark.anyio
async def test_revoke_session_rejects_without_a_csrf_token(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        login = await _login(client)
        _attach_session_cookies(client, login)

        response = await client.delete("/review/session", headers={"Origin": _ORIGIN})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "review_csrf_rejected"


@pytest.mark.anyio
async def test_revoke_session_rejects_a_mismatched_csrf_token(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        login = await _login(client)
        _attach_session_cookies(client, login)

        response = await client.delete(
            "/review/session",
            headers={"Origin": _ORIGIN, CSRF_HEADER_NAME: "wrong-token"},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "review_csrf_rejected"


@pytest.mark.anyio
async def test_revoke_session_rejects_a_mismatched_origin(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        login = await _login(client)
        _attach_session_cookies(client, login)

        response = await client.delete(
            "/review/session",
            headers={
                "Origin": "https://attacker.example",
                CSRF_HEADER_NAME: login.cookies[CSRF_COOKIE_NAME],
            },
        )

    assert response.status_code == 403


@pytest.mark.anyio
async def test_read_session_returns_the_current_actor(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        login = await _login(client)
        _attach_session_cookies(client, login)

        response = await client.get("/review/session")

    assert response.status_code == 200
    assert response.json() == {"actor_id": "reviewer-1", "role": "reviewer"}


@pytest.mark.anyio
async def test_read_session_rejects_a_missing_session(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, _repository):
        response = await client.get("/review/session")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_review_session"


@pytest.mark.anyio
async def test_read_session_rejects_an_expired_session(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, repository):
        login = await _login(client)
        _attach_session_cookies(client, login)
        digest = sha256(login.cookies[SESSION_COOKIE_NAME].encode()).hexdigest()
        resolved = repository.resolve_session(digest)
        assert resolved is not None
        with repository._connection() as connection:
            connection.execute(
                "UPDATE review_sessions SET expires_at = ? WHERE session_digest = ?",
                ("2000-01-01T00:00:00+00:00", digest),
            )

        response = await client.get("/review/session")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_review_session"


@pytest.mark.anyio
async def test_read_session_rejects_a_session_revoked_by_logout(
    tmp_path: Path,
) -> None:
    async with _client(tmp_path) as (client, _repository):
        login = await _login(client)
        _attach_session_cookies(client, login)
        await client.delete(
            "/review/session",
            headers={
                "Origin": _ORIGIN,
                CSRF_HEADER_NAME: login.cookies[CSRF_COOKIE_NAME],
            },
        )
        _attach_session_cookies(client, login)

        response = await client.get("/review/session")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_review_session"


@pytest.mark.anyio
async def test_revoke_session_repeated_logout_is_a_safe_no_op(tmp_path: Path) -> None:
    async with _client(tmp_path) as (client, repository):
        login = await _login(client)
        digest = sha256(login.cookies[SESSION_COOKIE_NAME].encode()).hexdigest()
        _attach_session_cookies(client, login)
        headers = {
            "Origin": _ORIGIN,
            CSRF_HEADER_NAME: login.cookies[CSRF_COOKIE_NAME],
        }

        first = await client.delete("/review/session", headers=headers)
        _attach_session_cookies(client, login)
        second = await client.delete("/review/session", headers=headers)

    assert first.status_code == 204
    assert second.status_code == 204
    revoked = repository.resolve_session(digest)
    assert revoked is not None
    assert revoked.revoked_at is not None
