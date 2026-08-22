"""Constant-time review actor authentication and session-policy tests."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest

from veridoc.review.auth import (
    SESSION_TTL,
    InvalidReviewCredentialsError,
    authenticate_actor,
    generate_csrf_token,
    hash_session_token,
    is_session_active,
    issue_session,
    verify_session_token,
)
from veridoc.review.config import ReviewActor, ReviewActorDirectory
from veridoc.review.models import ReviewSession

_REVIEWER_SECRET = "reviewer-secret-value"
_ADMIN_SECRET = "admin-secret-value"
_NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)


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


def _session(**overrides: object) -> ReviewSession:
    issued = issue_session(now=_NOW)
    fields: dict[str, object] = {
        "session_digest": issued.digest,
        "actor_id": "reviewer-1",
        "created_at": _NOW,
        "expires_at": issued.expires_at,
        "revoked_at": None,
    }
    fields.update(overrides)
    return ReviewSession(**fields)


def test_issue_session_generates_a_high_entropy_token_and_fixed_expiry() -> None:
    first = issue_session(now=_NOW)
    second = issue_session(now=_NOW)

    assert first.token != second.token
    assert len(first.token) >= 32
    assert first.digest == hash_session_token(first.token)
    assert first.expires_at == _NOW + SESSION_TTL


def test_verify_session_token_accepts_only_the_matching_token() -> None:
    issued = issue_session(now=_NOW)
    session = _session(session_digest=issued.digest)

    assert verify_session_token(issued.token, session)
    assert not verify_session_token("wrong-token", session)


def test_is_session_active_true_before_expiry_and_without_revocation() -> None:
    session = _session()
    assert is_session_active(session, now=_NOW)
    assert is_session_active(session, now=session.expires_at - timedelta(seconds=1))


def test_is_session_active_false_at_or_after_expiry() -> None:
    session = _session()
    assert not is_session_active(session, now=session.expires_at)
    assert not is_session_active(session, now=session.expires_at + timedelta(seconds=1))


def test_is_session_active_false_once_revoked_even_before_expiry() -> None:
    session = _session(revoked_at=_NOW)
    assert not is_session_active(session, now=_NOW)


def test_generate_csrf_token_returns_distinct_high_entropy_values() -> None:
    first = generate_csrf_token()
    second = generate_csrf_token()

    assert first != second
    assert len(first) >= 32
