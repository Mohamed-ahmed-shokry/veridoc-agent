"""OpenAI Responses API adapter for structured invoice extraction."""

from __future__ import annotations

import asyncio
import base64
from asyncio import to_thread

from openai import APIError, AsyncOpenAI
from openai.types.responses import ResponseInputContentParam, ResponseInputParam
from pydantic import ValidationError

from veridoc.extraction.config import OpenAIExtractionSettings
from veridoc.extraction.models import InvoiceExtraction
from veridoc.extraction.protocol import (
    ExtractionProcessingError,
    ExtractionRequest,
    ExtractionUnavailableError,
)

_INSTRUCTIONS = """Extract structured data from the supplied invoice or purchase order.
Use the OCR text and page images together. Return only the requested typed fields.
Do not invent a missing value. Classify documents as invoice, purchase_order, or
unknown. Record ambiguities in uncertainties. Attach page-level evidence to
important header fields and line items using only the provided page numbers and
the applicable ocr_text or page_image source. Do not perform verification,
anomaly detection, arithmetic reconciliation, explanations, or verdicts.
"""
_PROVIDER_CALL_TIMEOUT_SECONDS = 120.0


class OpenAIResponsesExtractor:
    """Call the OpenAI Responses API through the structured extractor protocol."""

    def __init__(
        self, settings: OpenAIExtractionSettings, client: AsyncOpenAI | None = None
    ) -> None:
        self._settings = settings
        self._client = client or AsyncOpenAI(api_key=settings.api_key)

    async def aclose(self) -> None:
        """Close the provider client owned by this adapter."""
        await self._client.close()

    async def extract(self, request: ExtractionRequest) -> InvoiceExtraction:
        """Extract one invoice without exposing provider failures to callers."""
        try:
            response_input = await to_thread(_build_response_input, request)
            async with asyncio.timeout(_PROVIDER_CALL_TIMEOUT_SECONDS):
                response = await self._client.responses.parse(
                    model=self._settings.model,
                    instructions=_INSTRUCTIONS,
                    input=response_input,
                    text_format=InvoiceExtraction,
                    store=False,
                )
        except TimeoutError as exc:
            raise ExtractionUnavailableError from exc
        except APIError as exc:
            raise ExtractionUnavailableError from exc
        except (TypeError, ValidationError, ValueError) as exc:
            raise ExtractionProcessingError from exc

        extracted = getattr(response, "output_parsed", None)
        if not isinstance(extracted, InvoiceExtraction):
            raise ExtractionProcessingError
        return extracted.model_copy(
            update={"ocr_confidence": request.document.confidence}
        )


def _build_response_input(request: ExtractionRequest) -> ResponseInputParam:
    """Build one multimodal Responses message from normalized OCR pages."""
    content: list[ResponseInputContentParam] = [
        {"type": "input_text", "text": _format_ocr_pages(request)}
    ]
    content.extend(
        {
            "type": "input_image",
            "image_url": _as_data_url(page.image_bytes),
            "detail": "high",
        }
        for page in request.page_images
    )
    return [{"role": "user", "content": content}]


def _format_ocr_pages(request: ExtractionRequest) -> str:
    """Label OCR pages so the model can align text evidence with images."""
    return "\n\n".join(
        f"--- OCR page {page_number} ---\n{page.text}"
        for page_number, page in enumerate(request.document.pages, start=1)
    )


def _as_data_url(image_bytes: bytes) -> str:
    """Return one in-memory PNG as a Responses-compatible image data URL."""
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"
