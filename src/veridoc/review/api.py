"""Authenticated FastAPI routes for the Phase 9 review workflow."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from veridoc.ingestion.dependencies import get_validated_upload
from veridoc.ingestion.models import ValidatedUpload
from veridoc.ocr.protocol import OCRProcessingError, OCRUnavailableError
from veridoc.processing.dependencies import get_processing_service
from veridoc.processing.service import ProcessingService
from veridoc.review.auth import (
    SESSION_TTL,
    InvalidReviewCredentialsError,
    authenticate_actor,
    generate_csrf_token,
    hash_session_token,
    is_session_active,
    issue_session,
)
from veridoc.review.config import (
    ReviewActorDirectory,
    ReviewAuthenticationUnavailableError,
    ReviewOriginSettings,
    ReviewStoreSettings,
)
from veridoc.review.models import (
    ActorId,
    ActorRole,
    CaseDetail,
    IdempotencyKey,
    IdempotentRequest,
    build_review_snapshot,
)
from veridoc.review.persistence.sqlite import SQLiteReviewRepository
from veridoc.review.protocol import ReviewDataUnavailableError

router = APIRouter(prefix="/review", tags=["review"])

SESSION_COOKIE_NAME = "veridoc_review_session"
CSRF_COOKIE_NAME = "veridoc_review_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"


class SessionResponse(BaseModel):
    """Safe post-authentication identity; never the session token itself."""

    model_config = ConfigDict(extra="forbid")

    actor_id: ActorId
    role: ActorRole


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


def require_origin_match(
    request: Request,
    origin: Annotated[ReviewOriginSettings, Depends(get_review_origin_settings)],
) -> None:
    """Require the request's ``Origin`` header to exactly match the configured
    review origin, before any state-changing work is reachable.
    """
    if request.headers.get("origin") != origin.origin:
        raise _csrf_rejected()


def require_csrf_protection(
    request: Request,
    _origin_match: Annotated[None, Depends(require_origin_match)],
) -> None:
    """Require exact-origin validation plus a matching double-submit CSRF token."""
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get(CSRF_HEADER_NAME)
    if (
        not cookie_token
        or not header_token
        or not secrets.compare_digest(cookie_token, header_token)
    ):
        raise _csrf_rejected()


@router.post(
    "/session",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_review_session(
    request: Request,
    response: Response,
    _origin_match: Annotated[None, Depends(require_origin_match)],
    repository: Annotated[SQLiteReviewRepository, Depends(get_review_repository)],
    directory: Annotated[ReviewActorDirectory, Depends(get_review_actor_directory)],
) -> SessionResponse:
    """Exchange a configured actor credential for a browser session cookie."""
    try:
        actor = authenticate_actor(request.headers.get("Authorization"), directory)
    except InvalidReviewCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": exc.code, "message": exc.message},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    issued = issue_session(now=datetime.now(UTC))
    repository.create_session(
        session_digest=issued.digest,
        actor_id=actor.actor_id,
        expires_at=issued.expires_at,
    )
    max_age = int(SESSION_TTL.total_seconds())
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=issued.token,
        max_age=max_age,
        path=router.prefix,
        secure=True,
        httponly=True,
        samesite="strict",
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=generate_csrf_token(),
        max_age=max_age,
        path=router.prefix,
        secure=True,
        httponly=False,
        samesite="strict",
    )
    return SessionResponse(actor_id=actor.actor_id, role=actor.role)


@router.delete(
    "/session",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def revoke_review_session(
    request: Request,
    _csrf: Annotated[None, Depends(require_csrf_protection)],
    repository: Annotated[SQLiteReviewRepository, Depends(get_review_repository)],
) -> Response:
    """Revoke the current browser session; a repeat logout is a safe no-op."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        repository.revoke_session(hash_session_token(token))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path=router.prefix)
    response.delete_cookie(key=CSRF_COOKIE_NAME, path=router.prefix)
    return response


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


IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"
_idempotency_key_adapter: TypeAdapter[str] = TypeAdapter(IdempotencyKey)


def _require_idempotency_key(request: Request) -> str:
    try:
        return _idempotency_key_adapter.validate_python(
            request.headers.get(IDEMPOTENCY_KEY_HEADER)
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "missing_idempotency_key",
                "message": "A valid Idempotency-Key header is required.",
            },
        ) from exc


@router.post(
    "/cases",
    response_model=CaseDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_review_case(
    request: Request,
    actor: Annotated[AuthenticatedActor, Depends(require_review_actor)],
    _csrf: Annotated[None, Depends(require_csrf_protection)],
    upload: Annotated[ValidatedUpload, Depends(get_validated_upload)],
    service: Annotated[ProcessingService, Depends(get_processing_service)],
    repository: Annotated[SQLiteReviewRepository, Depends(get_review_repository)],
) -> CaseDetail:
    """Process a bounded document and atomically create a case.

    A retry with the same ``Idempotency-Key`` and document returns the
    original case; reuse with a different document conflicts.
    """
    idempotency_key = _require_idempotency_key(request)
    try:
        result = await service.process(upload)
    except OCRUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except OCRProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    snapshot = build_review_snapshot(result)
    return repository.create_case(
        snapshot=snapshot,
        creator_actor_id=actor.actor_id,
        request_id=request.state.request_id,
        idempotent_request=IdempotentRequest(
            actor_id=actor.actor_id,
            operation="create_case",
            idempotency_key=idempotency_key,
            request_digest=hashlib.sha256(upload.data).hexdigest(),
        ),
    )


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


def _csrf_rejected() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "review_csrf_rejected",
            "message": "The request origin or CSRF token is invalid.",
        },
    )
