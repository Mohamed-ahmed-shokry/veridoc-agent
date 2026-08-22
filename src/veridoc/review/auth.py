"""Constant-time credential authentication for Phase 9 review actors."""

from __future__ import annotations

import secrets
from hashlib import sha256

from veridoc.review.config import ReviewActor, ReviewActorDirectory


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
