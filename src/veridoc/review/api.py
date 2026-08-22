"""Authenticated FastAPI routes for the Phase 9 review workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from veridoc.review.auth import hash_session_token, is_session_active
from veridoc.review.config import (
    ReviewActorDirectory,
    ReviewAuthenticationUnavailableError,
    ReviewOriginSettings,
    ReviewStoreSettings,
)
from veridoc.review.models import ActorId, ActorRole
from veridoc.review.persistence.sqlite import SQLiteReviewRepository
from veridoc.review.protocol import ReviewDataUnavailableError

router = APIRouter(prefix="/review", tags=["review"])

SESSION_COOKIE_NAME = "veridoc_review_session"


@dataclass(frozen=True, slots=True)
class AuthenticatedActor:
    """One resolved actor identity for the current authenticated request."""

    actor_id: ActorId
    role: ActorRole


def get_review_repository() -> SQLiteReviewRepository:
    """Open and initialize the configured dedicated review-store database."""
    try:
        settings = ReviewStoreSettings.from_environment()
        repository = SQLiteReviewRepository(settings.database_path)
        repository.initialize()
    except ReviewDataUnavailableError as exc:
        raise _service_unavailable(exc.code, exc.message) from exc
    return repository


def get_review_actor_directory() -> ReviewActorDirectory:
    """Load the configured operator-managed review actor directory."""
    try:
        return ReviewActorDirectory.from_environment()
    except ReviewAuthenticationUnavailableError as exc:
        raise _service_unavailable(exc.code, exc.message) from exc


def get_review_origin_settings() -> ReviewOriginSettings:
    """Require the configured HTTPS review origin."""
    try:
        return ReviewOriginSettings.from_environment()
    except ReviewAuthenticationUnavailableError as exc:
        raise _service_unavailable(exc.code, exc.message) from exc


def require_review_actor(
    request: Request,
    _origin: Annotated[ReviewOriginSettings, Depends(get_review_origin_settings)],
    repository: Annotated[SQLiteReviewRepository, Depends(get_review_repository)],
    directory: Annotated[ReviewActorDirectory, Depends(get_review_actor_directory)],
) -> AuthenticatedActor:
    """Resolve the actor authenticated by the current browser session cookie."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise _invalid_session()

    session = repository.resolve_session(hash_session_token(token))
    if session is None or not is_session_active(session, now=datetime.now(UTC)):
        raise _invalid_session()

    actor = directory.get(session.actor_id)
    if actor is None:
        raise _invalid_session()
    return AuthenticatedActor(actor_id=actor.actor_id, role=actor.role)


def _invalid_session() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "invalid_review_session",
            "message": "The review session is missing, expired, or invalid.",
        },
    )


def _service_unavailable(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={"code": code, "message": message},
    )
