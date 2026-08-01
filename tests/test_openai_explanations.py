"""OpenAI Responses explanation adapter tests without network access."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import APIConnectionError

from veridoc.explanation.config import OpenAIExplanationSettings
from veridoc.explanation.openai_responses import OpenAIResponsesExplainer
from veridoc.explanation.protocol import (
    ExplanationDraft,
    ExplanationDraftResult,
    ExplanationProcessingError,
    ExplanationRequest,
    ExplanationUnavailableError,
)
from veridoc.verification.models import VerificationFinding, VerificationResult


class _FakeResponses:
    def __init__(self, response: object | Exception) -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []

    async def parse(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class _FakeClient:
    def __init__(self, response: object | Exception) -> None:
        self.responses = _FakeResponses(response)


def _request() -> ExplanationRequest:
    return ExplanationRequest.from_verification(
        VerificationResult(
            findings=[
                VerificationFinding(
                    finding_type="historical_total_outlier",
                    severity="high",
                    explanation="The invoice total is outside the vendor's established range.",
                    comparison_source="vendor_history",
                    deterministic_rule="absolute_z_score >= 3",
                    observed_value="18400.00",
                    expected_range=("5600.00", "8800.00"),
                )
            ]
        )
    )


def _settings() -> OpenAIExplanationSettings:
    return OpenAIExplanationSettings(api_key="test-key", model="test-model")


@pytest.mark.anyio
async def test_adapter_sends_only_verified_findings_to_structured_parsing() -> None:
    client = _FakeClient(
        SimpleNamespace(
            output_parsed=ExplanationDraftResult(
                drafts=[
                    ExplanationDraft(
                        finding_index=0,
                        narrative="Confirm the supplied evidence before taking action.",
                    )
                ]
            )
        )
    )
    explainer = OpenAIResponsesExplainer(_settings(), client=client)  # type: ignore[arg-type]

    result = await explainer.explain(_request())

    assert result.drafts[0].finding_index == 0
    call = client.responses.calls[0]
    assert call["model"] == "test-model"
    assert call["text_format"] is ExplanationDraftResult
    assert call["store"] is False
    evidence = json.loads(call["input"][0]["content"][0]["text"])
    assert evidence["findings"][0]["observed_value"] == "18400.00"


@pytest.mark.anyio
async def test_adapter_maps_provider_failures_to_safe_unavailability() -> None:
    error = APIConnectionError(request=httpx.Request("POST", "https://example.test"))
    explainer = OpenAIResponsesExplainer(
        _settings(),
        client=_FakeClient(error),  # type: ignore[arg-type]
    )

    with pytest.raises(ExplanationUnavailableError):
        await explainer.explain(_request())


@pytest.mark.anyio
async def test_adapter_rejects_missing_structured_output() -> None:
    explainer = OpenAIResponsesExplainer(
        _settings(),
        client=_FakeClient(SimpleNamespace(output_parsed=None)),  # type: ignore[arg-type]
    )

    with pytest.raises(ExplanationProcessingError):
        await explainer.explain(_request())
