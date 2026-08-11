"""Environment configuration for the explanation provider."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from veridoc.explanation.protocol import ExplanationUnavailableError


@dataclass(frozen=True, slots=True)
class OpenAIExplanationSettings:
    """Required configuration for the OpenAI explanation adapter."""

    api_key: str = field(repr=False)
    model: str

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> OpenAIExplanationSettings:
        """Load non-empty provider settings without exposing missing-value details."""
        values = os.environ if environment is None else environment
        api_key = values.get("OPENAI_API_KEY", "").strip()
        model = values.get("VERIDOC_LLM_MODEL", "").strip()
        if not api_key or not model:
            raise ExplanationUnavailableError
        return cls(api_key=api_key, model=model)
