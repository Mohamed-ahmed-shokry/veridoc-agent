"""Constant-time review actor authentication tests."""

from hashlib import sha256

import pytest

from veridoc.review.auth import InvalidReviewCredentialsError, authenticate_actor
from veridoc.review.config import ReviewActor, ReviewActorDirectory

_REVIEWER_SECRET = "reviewer-secret-value"
_ADMIN_SECRET = "admin-secret-value"


def _digest(secret: str) -> str:
    return sha256(secret.encode("utf-8")).hexdigest()


def _directory(*actors: ReviewActor) -> ReviewActorDirectory:
    return ReviewActorDirectory(
        _actors_by_id={actor.actor_id: actor for actor in actors}
    )


def _reviewer() -> ReviewActor:
    return ReviewActor(
        actor_id="reviewer-1", role="reviewer", secret_digest=_digest(_REVIEWER_SECRET)
    )


def _admin() -> ReviewActor:
    return ReviewActor(
        actor_id="admin-1", role="review_admin", secret_digest=_digest(_ADMIN_SECRET)
    )


def test_authenticate_actor_matches_a_valid_reviewer_credential() -> None:
    directory = _directory(_reviewer(), _admin())

    actor = authenticate_actor(f"Bearer {_REVIEWER_SECRET}", directory)

    assert actor.actor_id == "reviewer-1"
    assert actor.role == "reviewer"


def test_authenticate_actor_matches_a_valid_admin_credential_among_duplicates() -> None:
    directory = _directory(_reviewer(), _admin())

    actor = authenticate_actor(f"Bearer {_ADMIN_SECRET}", directory)

    assert actor.actor_id == "admin-1"
    assert actor.role == "review_admin"


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "",
        "Bearer",
        "Bearer ",
        "Basic secret",
        "bearer-no-space",
        f"Bearer {_REVIEWER_SECRET}\n",
    ],
)
def test_authenticate_actor_rejects_malformed_authorization_headers(
    authorization: str | None,
) -> None:
    directory = _directory(_reviewer())

    with pytest.raises(InvalidReviewCredentialsError):
        authenticate_actor(authorization, directory)


def test_authenticate_actor_rejects_an_unknown_credential() -> None:
    directory = _directory(_reviewer())

    with pytest.raises(InvalidReviewCredentialsError):
        authenticate_actor("Bearer wrong-secret", directory)


def test_authenticate_actor_rejects_every_credential_against_an_empty_directory() -> (
    None
):
    directory = _directory()

    with pytest.raises(InvalidReviewCredentialsError):
        authenticate_actor(f"Bearer {_REVIEWER_SECRET}", directory)


def test_authenticate_actor_is_case_sensitive_only_on_the_scheme_value() -> None:
    directory = _directory(_reviewer())

    actor = authenticate_actor(f"bearer {_REVIEWER_SECRET}", directory)
    assert actor.actor_id == "reviewer-1"

    with pytest.raises(InvalidReviewCredentialsError):
        authenticate_actor(f"BEARER {_REVIEWER_SECRET.upper()}", directory)
