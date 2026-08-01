"""Extraction service composition tests."""

from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from veridoc.extraction.models import InvoiceExtraction
from veridoc.extraction.protocol import ExtractionRequest
from veridoc.extraction.service import ExtractionService
from veridoc.ingestion.validation import validate_upload
from veridoc.ocr.models import OCRPageResult


class _FakeOCREngine:
    def recognize(self, image: Image.Image) -> OCRPageResult:
        assert image.mode == "RGB"
        return OCRPageResult(text="Invoice No: INV-001", confidence=93.0)


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


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (16, 8), color="white").save(output, format="PNG")
    return output.getvalue()


@pytest.mark.anyio
async def test_service_passes_ocr_text_and_normalized_images_to_the_graph() -> None:
    extractor = _FakeExtractor()
    service = ExtractionService(_FakeOCREngine(), extractor)
    upload = validate_upload(
        _png_bytes(),
        filename="fictional-invoice.png",
        declared_content_type="image/png",
    )

    result = await service.process(upload)

    assert result.invoice_number == "INV-001"
    assert result.ocr_confidence == 93.0
    assert extractor.requests[0].document.text == "Invoice No: INV-001"
    assert len(extractor.requests[0].page_images) == 1
