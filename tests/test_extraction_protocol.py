"""Structured extractor boundary tests."""

import pytest

from veridoc.extraction.models import InvoiceExtraction
from veridoc.extraction.protocol import ExtractionRequest, StructuredExtractor
from veridoc.ocr.models import OCRDocumentResult, OCRPageResult, RenderedPage


class _FakeExtractor:
    async def extract(self, request: ExtractionRequest) -> InvoiceExtraction:
        assert request.document.text == "Fictional invoice"
        return InvoiceExtraction(document_type="invoice")


def test_request_requires_page_images_to_match_ocr_pages() -> None:
    document = OCRDocumentResult(
        media_type="image/png",
        pages=(OCRPageResult(text="Fictional invoice", confidence=90.0),),
    )

    request = ExtractionRequest(
        document=document,
        page_images=(RenderedPage(page_number=1, image_bytes=b"image"),),
    )

    assert isinstance(_FakeExtractor(), StructuredExtractor)
    assert request.page_images[0].page_number == 1

    with pytest.raises(ValueError, match="align"):
        ExtractionRequest(
            document=document,
            page_images=(RenderedPage(page_number=2, image_bytes=b"image"),),
        )
