"""Constant-time credential authentication for Phase 9 review actors."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from hashlib import sha256

from veridoc.review.config import ReviewActor, ReviewActorDirectory
from veridoc.review.models import ReviewSession

SESSION_TOKEN_BYTES = 32
SESSION_TTL = timedelta(hours=12)


class InvalidReviewCredentialsError(RuntimeError):
    """Raised for every missing, malformed, unknown, or incorrect credential."""

    code = "invalid_review_credentials"
    message = "Review credentials are invalid."

    def __init__(self) -> None:
        super().__init__(self.message)


def authenticate_actor(
    authorization: str | None, directory: ReviewActorDirectory
) -> ReviewActor:
    """Return the actor matching one constant-time compared bearer credential.

    Every configured actor's stored digest is compared, without
    short-circuiting on the first match, so response timing does not reveal
    which actor (if any) a presented credential belongs to.
    """
    scheme, separator, candidate = (authorization or "").partition(" ")
    well_formed = separator == " " and scheme.lower() == "bearer" and bool(candidate)
    presented_digest = sha256(candidate.encode("utf-8")).hexdigest()

    matched: ReviewActor | None = None
    for actor in directory.actors():
        if secrets.compare_digest(presented_digest, actor.secret_digest):
            matched = actor

    if not well_formed or matched is None:
        raise InvalidReviewCredentialsError
    return matched


@dataclass(frozen=True, slots=True)
class IssuedSession:
    """One newly issued opaque session token and its server-stored digest."""

    token: str = field(repr=False)
    digest: str
    expires_at: datetime


def hash_session_token(token: str) -> str:
    """Return the stored digest for one opaque session token."""
    return sha256(token.encode("utf-8")).hexdigest()


def issue_session(*, now: datetime) -> IssuedSession:
    """Generate one new high-entropy opaque session token with a fixed expiry."""
    token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
    return IssuedSession(
        token=token,
        digest=hash_session_token(token),
        expires_at=now + SESSION_TTL,
    )


def verify_session_token(token: str, session: ReviewSession) -> bool:
    """Return whether one presented token matches a session's digest, constant-time."""
    return secrets.compare_digest(hash_session_token(token), session.session_digest)


def is_session_active(session: ReviewSession, *, now: datetime) -> bool:
    """Return whether a persisted session is unrevoked and not yet expired."""
    if session.revoked_at is not None:
        return False
    return now < session.expires_at
