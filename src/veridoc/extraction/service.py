"""Application service composing OCR with the Phase 2 extraction graph."""

from __future__ import annotations

from asyncio import to_thread

from veridoc.extraction.graph import build_extraction_graph
from veridoc.extraction.models import InvoiceExtraction
from veridoc.extraction.protocol import (
    ExtractionProcessingError,
    ExtractionRequest,
    StructuredExtractor,
)
from veridoc.ingestion.models import ValidatedUpload
from veridoc.ocr.protocol import OCREngine
from veridoc.ocr.service import OCRService


class ExtractionService:
    """Run validated OCR and structured extraction for one document."""

    def __init__(self, ocr_engine: OCREngine, extractor: StructuredExtractor) -> None:
        self._ocr_engine = ocr_engine
        self._graph = build_extraction_graph(extractor)

    async def process(self, upload: ValidatedUpload) -> InvoiceExtraction:
        """Return the graph extraction after one normalized OCR pass."""
        bundle = await to_thread(
            OCRService(self._ocr_engine).process_with_page_images,
            upload,
        )
        state = await self._graph.ainvoke(
            {
                "request": ExtractionRequest(
                    document=bundle.document,
                    page_images=bundle.page_images,
                )
            }
        )
        extraction = state.get("extraction")
        if not isinstance(extraction, InvoiceExtraction):
            raise ExtractionProcessingError
        return extraction
