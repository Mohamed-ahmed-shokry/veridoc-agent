"""Explanation provider configuration tests."""

import pytest

from veridoc.explanation.config import OpenAIExplanationSettings
from veridoc.explanation.protocol import ExplanationUnavailableError


def test_settings_load_the_shared_openai_provider_values() -> None:
    settings = OpenAIExplanationSettings.from_environment(
        {"OPENAI_API_KEY": "test-key", "VERIDOC_LLM_MODEL": "test-model"}
    )

    assert settings.api_key == "test-key"
    assert settings.model == "test-model"


@pytest.mark.parametrize(
    "environment",
    [
        {},
        {"OPENAI_API_KEY": "test-key"},
        {"VERIDOC_LLM_MODEL": "test-model"},
        {"OPENAI_API_KEY": " ", "VERIDOC_LLM_MODEL": "test-model"},
    ],
)
def test_settings_reject_missing_or_blank_values(environment: dict[str, str]) -> None:
    with pytest.raises(ExplanationUnavailableError):
        OpenAIExplanationSettings.from_environment(environment)
