"""OpenAI Responses extraction adapter tests without network access."""

from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from openai import APIConnectionError

from veridoc.extraction import openai_responses
from veridoc.extraction.config import OpenAIExtractionSettings
from veridoc.extraction.models import InvoiceExtraction
from veridoc.extraction.openai_responses import OpenAIResponsesExtractor
from veridoc.extraction.protocol import (
    ExtractionProcessingError,
    ExtractionRequest,
    ExtractionUnavailableError,
)
from veridoc.ocr.models import OCRDocumentResult, OCRPageResult, RenderedPage


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
        self.closed = False

    async def close(self) -> None:
        self.closed = True


def _request() -> ExtractionRequest:
    return ExtractionRequest(
        document=OCRDocumentResult(
            media_type="image/png",
            pages=(
                OCRPageResult(
                    text="Invoice No: INV-001\nTotal: USD 18,400.00", confidence=91.0
                ),
            ),
        ),
        page_images=(RenderedPage(page_number=1, image_bytes=b"fictional-image"),),
    )


def _settings() -> OpenAIExtractionSettings:
    return OpenAIExtractionSettings(api_key="test-key", model="test-model")


@pytest.mark.anyio
async def test_adapter_sends_ocr_and_page_images_and_preserves_ocr_confidence() -> None:
    client = _FakeClient(
        SimpleNamespace(
            output_parsed=InvoiceExtraction(
                document_type="invoice",
                invoice_number="INV-001",
                ocr_confidence=1.0,
            )
        )
    )
    extractor = OpenAIResponsesExtractor(_settings(), client=client)  # type: ignore[arg-type]

    result = await extractor.extract(_request())

    assert result.ocr_confidence == 91.0
    call = client.responses.calls[0]
    assert call["model"] == "test-model"
    assert call["text_format"] is InvoiceExtraction
    assert call["store"] is False
    content = call["input"][0]["content"]
    assert content[0] == {
        "type": "input_text",
        "text": "--- OCR page 1 ---\nInvoice No: INV-001\nTotal: USD 18,400.00",
    }
    assert content[1] == {
        "type": "input_image",
        "image_url": "data:image/png;base64,ZmljdGlvbmFsLWltYWdl",
        "detail": "high",
    }


@pytest.mark.anyio
async def test_adapter_builds_multimodal_input_off_the_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_loop_thread = threading.get_ident()
    builder_thread: int | None = None
    expected_input = [{"role": "user", "content": []}]

    def build_response_input(request: ExtractionRequest) -> Any:
        nonlocal builder_thread
        builder_thread = threading.get_ident()
        assert request == _request()
        return expected_input

    monkeypatch.setattr(openai_responses, "_build_response_input", build_response_input)
    client = _FakeClient(
        SimpleNamespace(output_parsed=InvoiceExtraction(document_type="invoice"))
    )
    extractor = OpenAIResponsesExtractor(_settings(), client=client)  # type: ignore[arg-type]

    await extractor.extract(_request())

    assert builder_thread is not None
    assert builder_thread != event_loop_thread
    assert client.responses.calls[0]["input"] is expected_input


@pytest.mark.anyio
async def test_adapter_closes_its_provider_client() -> None:
    client = _FakeClient(SimpleNamespace(output_parsed=None))
    extractor = OpenAIResponsesExtractor(_settings(), client=client)  # type: ignore[arg-type]

    await extractor.aclose()

    assert client.closed is True


@pytest.mark.anyio
async def test_adapter_maps_provider_timeout_to_safe_unavailability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeClient(SimpleNamespace(output_parsed=None))

    async def stalled_parse(**kwargs: Any) -> object:
        del kwargs
        await asyncio.sleep(0.05)
        return SimpleNamespace(output_parsed=None)

    monkeypatch.setattr(
        openai_responses,
        "_PROVIDER_CALL_TIMEOUT_SECONDS",
        0.001,
    )
    monkeypatch.setattr(client.responses, "parse", stalled_parse)
    extractor = OpenAIResponsesExtractor(_settings(), client=client)  # type: ignore[arg-type]

    with pytest.raises(ExtractionUnavailableError):
        await extractor.extract(_request())


@pytest.mark.anyio
async def test_adapter_maps_provider_failures_to_safe_unavailability() -> None:
    error = APIConnectionError(request=httpx.Request("POST", "https://example.test"))
    client = _FakeClient(error)
    extractor = OpenAIResponsesExtractor(_settings(), client=client)  # type: ignore[arg-type]

    with pytest.raises(ExtractionUnavailableError):
        await extractor.extract(_request())


@pytest.mark.anyio
@pytest.mark.parametrize("response", [SimpleNamespace(output_parsed=None), object()])
async def test_adapter_rejects_missing_structured_output(response: object) -> None:
    client = _FakeClient(response)
    extractor = OpenAIResponsesExtractor(_settings(), client=client)  # type: ignore[arg-type]

    with pytest.raises(ExtractionProcessingError):
        await extractor.extract(_request())
