"""Environment configuration for the dedicated Phase 9 review store."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from veridoc.review.protocol import ReviewDataUnavailableError

DEFAULT_REVIEW_DATABASE = "veridoc-review.sqlite3"
_DEFAULT_REFERENCE_DATABASE = "veridoc-reference.sqlite3"


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
