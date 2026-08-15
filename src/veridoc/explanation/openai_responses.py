"""OpenAI Responses adapter for evidence-grounded explanation proposals."""

from __future__ import annotations

import asyncio
import json

from openai import APIError, AsyncOpenAI
from openai.types.responses import ResponseInputParam
from pydantic import ValidationError

from veridoc.explanation.config import OpenAIExplanationSettings
from veridoc.explanation.protocol import (
    ExplanationDraftResult,
    ExplanationProcessingError,
    ExplanationRequest,
    ExplanationUnavailableError,
)

_INSTRUCTIONS = """Provide one short, action-oriented review guidance sentence for each
verified finding. Return the supplied finding_index for every finding exactly once.
Do not state, calculate, transform, or infer any number, amount, date, range, or
statistic. Do not make comparative or negated factual claims. Do not restate the
verified evidence. The application attaches all factual and numerical context after
your guidance. Use only the supplied verified findings and do not invent facts.
"""
_PROVIDER_CALL_TIMEOUT_SECONDS = 120.0


class OpenAIResponsesExplainer:
    """Call the OpenAI Responses API through the explanation provider protocol."""

    def __init__(
        self, settings: OpenAIExplanationSettings, client: AsyncOpenAI | None = None
    ) -> None:
        self._settings = settings
        self._client = client or AsyncOpenAI(api_key=settings.api_key)

    async def aclose(self) -> None:
        """Close the provider client owned by this adapter."""
        await self._client.close()

    async def explain(self, request: ExplanationRequest) -> ExplanationDraftResult:
        """Return structured explanation drafts without exposing provider failures."""
        try:
            async with asyncio.timeout(_PROVIDER_CALL_TIMEOUT_SECONDS):
                response = await self._client.responses.parse(
                    model=self._settings.model,
                    instructions=_INSTRUCTIONS,
                    input=_build_response_input(request),
                    text_format=ExplanationDraftResult,
                    store=False,
                )
        except TimeoutError as exc:
            raise ExplanationUnavailableError from exc
        except APIError as exc:
            raise ExplanationUnavailableError from exc
        except (TypeError, ValidationError, ValueError) as exc:
            raise ExplanationProcessingError from exc

        drafts = getattr(response, "output_parsed", None)
        if not isinstance(drafts, ExplanationDraftResult):
            raise ExplanationProcessingError
        return drafts


def _build_response_input(request: ExplanationRequest) -> ResponseInputParam:
    """Serialize canonical findings without uploading document or OCR content."""
    evidence = {
        "findings": [finding.model_dump(mode="json") for finding in request.findings]
    }
    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": json.dumps(evidence, separators=(",", ":")),
                }
            ],
        }
    ]
