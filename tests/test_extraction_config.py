"""Structured extraction configuration tests."""

import pytest

from veridoc.extraction.config import OpenAIExtractionSettings
from veridoc.extraction.protocol import ExtractionUnavailableError


def test_settings_load_required_provider_values() -> None:
    settings = OpenAIExtractionSettings.from_environment(
        {"OPENAI_API_KEY": "test-key", "VERIDOC_LLM_MODEL": "test-model"}
    )

    assert settings.api_key == "test-key"
    assert settings.model == "test-model"
    assert "test-key" not in repr(settings)
    assert "test-model" in repr(settings)


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
    with pytest.raises(ExtractionUnavailableError):
        OpenAIExtractionSettings.from_environment(environment)
