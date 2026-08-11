"""Environment configuration for the structured extraction provider."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from veridoc.extraction.protocol import ExtractionUnavailableError


@dataclass(frozen=True, slots=True)
class OpenAIExtractionSettings:
    """Required configuration for the OpenAI structured extraction adapter."""

    api_key: str = field(repr=False)
    model: str

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> OpenAIExtractionSettings:
        """Load non-empty provider settings without exposing missing-value details."""
        values = os.environ if environment is None else environment
        api_key = values.get("OPENAI_API_KEY", "").strip()
        model = values.get("VERIDOC_LLM_MODEL", "").strip()
        if not api_key or not model:
            raise ExtractionUnavailableError
        return cls(api_key=api_key, model=model)
