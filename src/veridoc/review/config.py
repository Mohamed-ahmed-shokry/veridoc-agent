"""Environment configuration for the dedicated Phase 9 review store."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from veridoc.review.models import ActorId, ActorRole
from veridoc.review.protocol import ReviewDataUnavailableError

DEFAULT_REVIEW_DATABASE = "veridoc-review.sqlite3"
_DEFAULT_REFERENCE_DATABASE = "veridoc-reference.sqlite3"
_SECRET_DIGEST_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_actor_id_adapter: TypeAdapter[str] = TypeAdapter(ActorId)
_actor_role_adapter: TypeAdapter[ActorRole] = TypeAdapter(ActorRole)


class ReviewAuthenticationUnavailableError(RuntimeError):
    """Raised when the server lacks a valid configured review actor directory."""

    code = "review_authentication_unavailable"
    message = "Review authentication is not available on this server."

    def __init__(self) -> None:
        super().__init__(self.message)


@dataclass(frozen=True, slots=True)
class ReviewStoreSettings:
    """Validated local review-store database path, distinct from reference data."""

    database_path: str

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> ReviewStoreSettings:
        """Load a review database path that never resolves onto reference data."""
        values = os.environ if environment is None else environment
        review_path = values.get("VERIDOC_REVIEW_DATABASE", "").strip()
        review_path = review_path or DEFAULT_REVIEW_DATABASE
        reference_path = values.get("VERIDOC_REFERENCE_DATABASE", "").strip()
        reference_path = reference_path or _DEFAULT_REFERENCE_DATABASE

        if Path(review_path).resolve() == Path(reference_path).resolve():
            raise ReviewDataUnavailableError
        return cls(database_path=review_path)


@dataclass(frozen=True, slots=True)
class ReviewActor:
    """One operator-managed actor identity and its fixed-length secret digest."""

    actor_id: str
    role: ActorRole
    secret_digest: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ReviewActorDirectory:
    """Validated local review actors loaded from an operator-managed file."""

    _actors_by_id: dict[str, ReviewActor] = field(repr=False)

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> ReviewActorDirectory:
        """Load and validate the configured external review actor file."""
        values = os.environ if environment is None else environment
        actors_path = values.get("VERIDOC_REVIEW_ACTORS_FILE", "").strip()
        if not actors_path:
            raise ReviewAuthenticationUnavailableError
        try:
            entries = json.loads(Path(actors_path).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReviewAuthenticationUnavailableError from exc
        return cls(_actors_by_id=_parse_actors(entries))

    def get(self, actor_id: str) -> ReviewActor | None:
        """Return one configured actor by ID, or ``None`` when unknown."""
        return self._actors_by_id.get(actor_id)

    def actors(self) -> Iterable[ReviewActor]:
        """Return every configured actor for constant-time credential scans."""
        return self._actors_by_id.values()


def _parse_actors(entries: object) -> dict[str, ReviewActor]:
    if not isinstance(entries, list) or not entries:
        raise ReviewAuthenticationUnavailableError

    actors: dict[str, ReviewActor] = {}
    seen_digests: set[str] = set()
    for entry in entries:
        actor = _parse_actor(entry)
        if actor.actor_id in actors or actor.secret_digest in seen_digests:
            raise ReviewAuthenticationUnavailableError
        actors[actor.actor_id] = actor
        seen_digests.add(actor.secret_digest)
    return actors


def _parse_actor(entry: object) -> ReviewActor:
    if not isinstance(entry, dict):
        raise ReviewAuthenticationUnavailableError
    try:
        actor_id = _actor_id_adapter.validate_python(entry.get("actor_id"))
        role = _actor_role_adapter.validate_python(entry.get("role"))
    except ValidationError as exc:
        raise ReviewAuthenticationUnavailableError from exc

    secret_digest = entry.get("secret_digest")
    if not isinstance(secret_digest, str) or not _SECRET_DIGEST_PATTERN.fullmatch(
        secret_digest
    ):
        raise ReviewAuthenticationUnavailableError
    return ReviewActor(actor_id=actor_id, role=role, secret_digest=secret_digest)


@dataclass(frozen=True, slots=True)
class ReviewOriginSettings:
    """Validated HTTPS origin required before the review UI is available."""

    origin: str

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> ReviewOriginSettings:
        """Require a configured HTTPS review origin with no path or query."""
        values = os.environ if environment is None else environment
        origin = values.get("VERIDOC_REVIEW_ORIGIN", "").strip()
        if not origin.startswith("https://"):
            raise ReviewAuthenticationUnavailableError
        remainder = origin[len("https://") :]
        host = remainder.split("/", 1)[0].split("?", 1)[0]
        if not host or host != remainder:
            raise ReviewAuthenticationUnavailableError
        return cls(origin=origin)
