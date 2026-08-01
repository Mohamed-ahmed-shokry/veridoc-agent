"""In-process tests for the Phase 2 structured extraction endpoint."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import httpx
import pytest
from PIL import Image

from veridoc.app import app, get_ocr_engine, get_structured_extractor
from veridoc.extraction.models import EvidenceReference, InvoiceExtraction
from veridoc.extraction.protocol import (
    ExtractionProcessingError,
    ExtractionRequest,
    ExtractionUnavailableError,
)
from veridoc.ocr.models import OCRPageResult


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (12, 8), color="white").save(output, format="PNG")
    return output.getvalue()


class _FakeOCREngine:
    def recognize(self, image: Image.Image) -> OCRPageResult:
        assert image.mode == "RGB"
        return OCRPageResult(text="Invoice No: INV-001", confidence=91.0)


class _FakeExtractor:
    async def extract(self, request: ExtractionRequest) -> InvoiceExtraction:
        return InvoiceExtraction(
            document_type="invoice",
            vendor_name="Fictional Supplies Ltd.",
            invoice_number="INV-001",
            currency="USD",
            total="18400.00",
            ocr_confidence=request.document.confidence,
            extraction_confidence=84.0,
            evidence={
                "invoice_number": [
                    EvidenceReference(
                        page_number=1,
                        source="ocr_text",
                        text_span="Invoice No: INV-001",
                    )
                ]
            },
        )


class _UnavailableExtractor:
    async def extract(self, request: ExtractionRequest) -> InvoiceExtraction:
        del request
        raise ExtractionUnavailableError


class _InvalidExtractor:
    async def extract(self, request: ExtractionRequest) -> InvoiceExtraction:
        del request
        raise ExtractionProcessingError


async def _post_file(extractor: Any) -> httpx.Response:
    app.dependency_overrides[get_ocr_engine] = _FakeOCREngine
    app.dependency_overrides[get_structured_extractor] = lambda: extractor
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.post(
                "/extract",
                files={"file": ("fictional-invoice.png", _png_bytes(), "image/png")},
            )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_extract_endpoint_returns_typed_evidence_linked_data() -> None:
    response = await _post_file(_FakeExtractor())

    assert response.status_code == 200
    assert response.json() == {
        "document_type": "invoice",
        "vendor_name": "Fictional Supplies Ltd.",
        "vendor_identifier": None,
        "invoice_number": "INV-001",
        "purchase_order_number": None,
        "invoice_date": None,
        "due_date": None,
        "currency": "USD",
        "subtotal": None,
        "tax": None,
        "discount": None,
        "total": "18400.00",
        "payment_terms": None,
        "line_items": [],
        "ocr_confidence": 91.0,
        "extraction_confidence": 84.0,
        "evidence": {
            "invoice_number": [
                {
                    "page_number": 1,
                    "source": "ocr_text",
                    "text_span": "Invoice No: INV-001",
                }
            ]
        },
        "uncertainties": [],
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("extractor", "status_code", "code"),
    [
        (_UnavailableExtractor(), 503, "extraction_unavailable"),
        (_InvalidExtractor(), 422, "extraction_processing_failed"),
    ],
)
async def test_extract_endpoint_returns_safe_provider_errors(
    extractor: Any, status_code: int, code: str
) -> None:
    response = await _post_file(extractor)

    assert response.status_code == status_code
    assert response.json()["detail"]["code"] == code
