"""Typed LangGraph extraction-node tests."""

import pytest

from veridoc.extraction.graph import build_extraction_graph
from veridoc.extraction.models import (
    EvidenceReference,
    InvoiceExtraction,
    InvoiceLineItem,
)
from veridoc.extraction.protocol import ExtractionProcessingError, ExtractionRequest
from veridoc.ocr.models import OCRDocumentResult, OCRPageResult, RenderedPage


class _FakeExtractor:
    def __init__(self, extraction: InvoiceExtraction | None = None) -> None:
        self.requests: list[ExtractionRequest] = []
        self._extraction = extraction

    async def extract(self, request: ExtractionRequest) -> InvoiceExtraction:
        self.requests.append(request)
        return self._extraction or InvoiceExtraction(
            document_type="invoice",
            invoice_number="INV-001",
            ocr_confidence=request.document.confidence,
        )


class _MalformedExtractor:
    async def extract(self, request: ExtractionRequest) -> object:
        del request
        return None


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


@pytest.mark.anyio
async def test_graph_rejects_malformed_extractor_results() -> None:
    graph = build_extraction_graph(_MalformedExtractor())
    request = ExtractionRequest(
        document=OCRDocumentResult(
            media_type="image/png",
            pages=(OCRPageResult(text="Invoice INV-001", confidence=92.0),),
        ),
        page_images=(RenderedPage(page_number=1, image_bytes=b"image"),),
    )

    with pytest.raises(ExtractionProcessingError):
        await graph.ainvoke({"request": request})


@pytest.mark.anyio
@pytest.mark.parametrize("location", ["header", "line_item"])
async def test_graph_rejects_evidence_for_a_page_outside_the_document(
    location: str,
) -> None:
    reference = EvidenceReference(page_number=2, source="ocr_text")
    extraction = InvoiceExtraction(
        document_type="invoice",
        evidence={"invoice_number": [reference]} if location == "header" else {},
        line_items=(
            [InvoiceLineItem(description="Fictional service", evidence=[reference])]
            if location == "line_item"
            else []
        ),
    )
    graph = build_extraction_graph(_FakeExtractor(extraction))
    request = ExtractionRequest(
        document=OCRDocumentResult(
            media_type="image/png",
            pages=(OCRPageResult(text="Invoice INV-001", confidence=92.0),),
        ),
        page_images=(RenderedPage(page_number=1, image_bytes=b"image"),),
    )

    with pytest.raises(ExtractionProcessingError):
        await graph.ainvoke({"request": request})


@pytest.mark.anyio
@pytest.mark.parametrize("span", ["Invoice INV-999", "   "])
async def test_graph_rejects_an_ocr_span_absent_from_its_page(span: str) -> None:
    extraction = InvoiceExtraction(
        document_type="invoice",
        evidence={
            "invoice_number": [
                EvidenceReference(
                    page_number=1,
                    source="ocr_text",
                    text_span=span,
                )
            ]
        },
    )
    graph = build_extraction_graph(_FakeExtractor(extraction))
    request = ExtractionRequest(
        document=OCRDocumentResult(
            media_type="image/png",
            pages=(OCRPageResult(text="Invoice INV-001", confidence=92.0),),
        ),
        page_images=(RenderedPage(page_number=1, image_bytes=b"image"),),
    )

    with pytest.raises(ExtractionProcessingError):
        await graph.ainvoke({"request": request})


@pytest.mark.anyio
async def test_graph_accepts_a_normalized_ocr_span_from_its_page() -> None:
    extraction = InvoiceExtraction(
        document_type="invoice",
        evidence={
            "invoice_number": [
                EvidenceReference(
                    page_number=1,
                    source="ocr_text",
                    text_span="invoice   inv-001",
                )
            ]
        },
    )
    graph = build_extraction_graph(_FakeExtractor(extraction))
    request = ExtractionRequest(
        document=OCRDocumentResult(
            media_type="image/png",
            pages=(OCRPageResult(text="Invoice\nINV-001", confidence=92.0),),
        ),
        page_images=(RenderedPage(page_number=1, image_bytes=b"image"),),
    )

    result = await graph.ainvoke({"request": request})

    assert result["extraction"] == extraction
