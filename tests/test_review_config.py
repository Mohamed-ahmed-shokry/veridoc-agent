"""Review-store database configuration tests."""

from pathlib import Path

import pytest

from veridoc.review.config import DEFAULT_REVIEW_DATABASE, ReviewStoreSettings
from veridoc.review.protocol import ReviewDataUnavailableError


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


def test_settings_allow_distinct_configured_paths() -> None:
    settings = ReviewStoreSettings.from_environment(
        {
            "VERIDOC_REVIEW_DATABASE": "review.sqlite3",
            "VERIDOC_REFERENCE_DATABASE": "reference.sqlite3",
        }
    )
    assert settings.database_path == "review.sqlite3"
