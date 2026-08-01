"""Typed LangGraph extraction-node tests."""

import pytest

from veridoc.extraction.graph import build_extraction_graph
from veridoc.extraction.models import InvoiceExtraction
from veridoc.extraction.protocol import ExtractionRequest
from veridoc.ocr.models import OCRDocumentResult, OCRPageResult, RenderedPage


class _FakeExtractor:
    def __init__(self) -> None:
        self.requests: list[ExtractionRequest] = []

    async def extract(self, request: ExtractionRequest) -> InvoiceExtraction:
        self.requests.append(request)
        return InvoiceExtraction(
            document_type="invoice",
            invoice_number="INV-001",
            ocr_confidence=request.document.confidence,
        )


@pytest.mark.anyio
async def test_graph_runs_the_typed_extraction_node() -> None:
    extractor = _FakeExtractor()
    graph = build_extraction_graph(extractor)
    request = ExtractionRequest(
        document=OCRDocumentResult(
            media_type="image/png",
            pages=(OCRPageResult(text="Invoice INV-001", confidence=92.0),),
        ),
        page_images=(RenderedPage(page_number=1, image_bytes=b"image"),),
    )

    result = await graph.ainvoke({"request": request})

    assert extractor.requests == [request]
    assert result["extraction"].invoice_number == "INV-001"
    assert result["extraction"].ocr_confidence == 92.0
