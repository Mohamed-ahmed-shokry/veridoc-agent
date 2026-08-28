"""Review-store and review-actor configuration tests."""

import json
import os
from pathlib import Path

import pytest

from veridoc.review.config import (
    DEFAULT_REVIEW_DATABASE,
    ReviewActorDirectory,
    ReviewAuthenticationUnavailableError,
    ReviewOriginSettings,
    ReviewStoreSettings,
)
from veridoc.review.protocol import ReviewDataUnavailableError

_SECRET_DIGEST = "a" * 64
_OTHER_SECRET_DIGEST = "b" * 64


def test_settings_default_to_a_dedicated_review_database_path() -> None:
    settings = ReviewStoreSettings.from_environment({})
    assert settings.database_path == DEFAULT_REVIEW_DATABASE


def test_settings_use_a_configured_review_database_path() -> None:
    settings = ReviewStoreSettings.from_environment(
        {"VERIDOC_REVIEW_DATABASE": "custom-review.sqlite3"}
    )
    assert settings.database_path == "custom-review.sqlite3"


def test_settings_reject_the_default_reference_database_path() -> None:
    with pytest.raises(ReviewDataUnavailableError):
        ReviewStoreSettings.from_environment(
            {"VERIDOC_REVIEW_DATABASE": "veridoc-reference.sqlite3"}
        )


def test_settings_reject_an_explicitly_configured_shared_path() -> None:
    with pytest.raises(ReviewDataUnavailableError):
        ReviewStoreSettings.from_environment(
            {
                "VERIDOC_REVIEW_DATABASE": "shared.sqlite3",
                "VERIDOC_REFERENCE_DATABASE": "shared.sqlite3",
            }
        )


def test_settings_reject_paths_that_resolve_to_the_same_file(tmp_path: Path) -> None:
    absolute = tmp_path / "data.sqlite3"
    with pytest.raises(ReviewDataUnavailableError):
        ReviewStoreSettings.from_environment(
            {
                "VERIDOC_REVIEW_DATABASE": f"{tmp_path}/./data.sqlite3",
                "VERIDOC_REFERENCE_DATABASE": str(absolute),
            }
        )


def test_settings_reject_hard_links_to_the_same_database(tmp_path: Path) -> None:
    review_path = tmp_path / "review.sqlite3"
    reference_path = tmp_path / "reference.sqlite3"
    review_path.write_bytes(b"database placeholder")
    os.link(review_path, reference_path)

    with pytest.raises(ReviewDataUnavailableError):
        ReviewStoreSettings.from_environment(
            {
                "VERIDOC_REVIEW_DATABASE": str(review_path),
                "VERIDOC_REFERENCE_DATABASE": str(reference_path),
            }
        )


def test_settings_allow_distinct_configured_paths() -> None:
    settings = ReviewStoreSettings.from_environment(
        {
            "VERIDOC_REVIEW_DATABASE": "review.sqlite3",
            "VERIDOC_REFERENCE_DATABASE": "reference.sqlite3",
        }
    )
    assert settings.database_path == "review.sqlite3"


def test_origin_settings_accept_a_bare_https_origin() -> None:
    settings = ReviewOriginSettings.from_environment(
        {"VERIDOC_REVIEW_ORIGIN": "https://review.example"}
    )
    assert settings.origin == "https://review.example"


def test_origin_settings_strip_surrounding_whitespace() -> None:
    settings = ReviewOriginSettings.from_environment(
        {"VERIDOC_REVIEW_ORIGIN": "  https://review.example  "}
    )
    assert settings.origin == "https://review.example"


def test_origin_settings_reject_a_missing_value() -> None:
    with pytest.raises(ReviewAuthenticationUnavailableError):
        ReviewOriginSettings.from_environment({})


def test_origin_settings_reject_a_non_https_scheme() -> None:
    with pytest.raises(ReviewAuthenticationUnavailableError):
        ReviewOriginSettings.from_environment(
            {"VERIDOC_REVIEW_ORIGIN": "http://review.example"}
        )


def test_origin_settings_reject_a_path() -> None:
    with pytest.raises(ReviewAuthenticationUnavailableError):
        ReviewOriginSettings.from_environment(
            {"VERIDOC_REVIEW_ORIGIN": "https://review.example/path"}
        )


def test_origin_settings_reject_a_query_with_no_path() -> None:
    with pytest.raises(ReviewAuthenticationUnavailableError):
        ReviewOriginSettings.from_environment(
            {"VERIDOC_REVIEW_ORIGIN": "https://review.example?x=1"}
        )


def test_origin_settings_reject_an_empty_host() -> None:
    with pytest.raises(ReviewAuthenticationUnavailableError):
        ReviewOriginSettings.from_environment({"VERIDOC_REVIEW_ORIGIN": "https://"})


@pytest.mark.parametrize(
    "origin",
    [
        "https://user@review.example",
        "https://user:secret@review.example",
        "https://review.example#fragment",
        "https://review.example#",
        "https://review.example?",
        "https://review.example\\path",
        "https://review.example:invalid",
        "https://review.example:70000",
        "https://review.example:",
        "https://review.example:0",
    ],
)
def test_origin_settings_reject_non_origin_url_variants(origin: str) -> None:
    with pytest.raises(ReviewAuthenticationUnavailableError):
        ReviewOriginSettings.from_environment({"VERIDOC_REVIEW_ORIGIN": origin})


def _write_actors(tmp_path: Path, entries: object) -> str:
    path = tmp_path / "actors.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return str(path)


def test_actor_directory_loads_valid_reviewer_and_admin_entries(
    tmp_path: Path,
) -> None:
    actors_path = _write_actors(
        tmp_path,
        [
            {
                "actor_id": "reviewer-1",
                "role": "reviewer",
                "secret_digest": _SECRET_DIGEST,
            },
            {
                "actor_id": "admin-1",
                "role": "review_admin",
                "secret_digest": _OTHER_SECRET_DIGEST,
            },
        ],
    )

    directory = ReviewActorDirectory.from_environment(
        {"VERIDOC_REVIEW_ACTORS_FILE": actors_path}
    )

    reviewer = directory.get("reviewer-1")
    assert reviewer is not None
    assert reviewer.role == "reviewer"
    assert reviewer.secret_digest == _SECRET_DIGEST
    assert directory.get("unknown-actor") is None


def test_actor_directory_requires_a_configured_file_path() -> None:
    with pytest.raises(ReviewAuthenticationUnavailableError):
        ReviewActorDirectory.from_environment({})


def test_actor_directory_rejects_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ReviewAuthenticationUnavailableError):
        ReviewActorDirectory.from_environment(
            {"VERIDOC_REVIEW_ACTORS_FILE": str(tmp_path / "missing.json")}
        )


@pytest.mark.parametrize(
    "contents",
    [
        "not json",
        "{}",
        "[]",
        "[1]",
        json.dumps([{"actor_id": "reviewer-1", "role": "reviewer"}]),
        json.dumps(
            [{"actor_id": "-bad-id", "role": "reviewer", "secret_digest": "a" * 64}]
        ),
        json.dumps(
            [{"actor_id": "reviewer-1", "role": "owner", "secret_digest": "a" * 64}]
        ),
        json.dumps(
            [{"actor_id": "reviewer-1", "role": "reviewer", "secret_digest": "short"}]
        ),
        json.dumps(
            [{"actor_id": "reviewer-1", "role": "reviewer", "secret_digest": "A" * 64}]
        ),
    ],
)
def test_actor_directory_rejects_malformed_content(
    tmp_path: Path, contents: str
) -> None:
    path = tmp_path / "actors.json"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(ReviewAuthenticationUnavailableError):
        ReviewActorDirectory.from_environment({"VERIDOC_REVIEW_ACTORS_FILE": str(path)})


def test_actor_directory_rejects_duplicate_actor_ids(tmp_path: Path) -> None:
    actors_path = _write_actors(
        tmp_path,
        [
            {
                "actor_id": "reviewer-1",
                "role": "reviewer",
                "secret_digest": _SECRET_DIGEST,
            },
            {
                "actor_id": "reviewer-1",
                "role": "review_admin",
                "secret_digest": _OTHER_SECRET_DIGEST,
            },
        ],
    )

    with pytest.raises(ReviewAuthenticationUnavailableError):
        ReviewActorDirectory.from_environment(
            {"VERIDOC_REVIEW_ACTORS_FILE": actors_path}
        )


def test_actor_directory_rejects_duplicate_secret_digests(tmp_path: Path) -> None:
    actors_path = _write_actors(
        tmp_path,
        [
            {
                "actor_id": "reviewer-1",
                "role": "reviewer",
                "secret_digest": _SECRET_DIGEST,
            },
            {
                "actor_id": "reviewer-2",
                "role": "reviewer",
                "secret_digest": _SECRET_DIGEST,
            },
        ],
    )

    with pytest.raises(ReviewAuthenticationUnavailableError):
        ReviewActorDirectory.from_environment(
            {"VERIDOC_REVIEW_ACTORS_FILE": actors_path}
        )


def test_actor_directory_repr_hides_secret_digests(tmp_path: Path) -> None:
    actors_path = _write_actors(
        tmp_path,
        [
            {
                "actor_id": "reviewer-1",
                "role": "reviewer",
                "secret_digest": _SECRET_DIGEST,
            }
        ],
    )

    directory = ReviewActorDirectory.from_environment(
        {"VERIDOC_REVIEW_ACTORS_FILE": actors_path}
    )

    assert _SECRET_DIGEST not in repr(directory.get("reviewer-1"))
