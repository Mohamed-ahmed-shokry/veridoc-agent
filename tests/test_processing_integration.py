"""Complete processing integration tests through the FastAPI dependency graph."""

from __future__ import annotations

from io import BytesIO

import httpx
import pytest
from PIL import Image

from veridoc.app import app, get_ocr_engine, get_structured_extractor
from veridoc.explanation.service import ExplanationService
from veridoc.extraction.models import InvoiceExtraction
from veridoc.extraction.protocol import ExtractionRequest
from veridoc.ocr.models import OCRPageResult
from veridoc.persistence.sqlite import SQLiteInvoiceRepository
from veridoc.processing.dependencies import get_explanation_service
from veridoc.verification.references import HistoricalInvoice


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


class _IntegrationOCREngine:
    def recognize(self, image: Image.Image) -> OCRPageResult:
        """Return deterministic OCR text for the synthetic upload."""
        assert image.mode == "RGB"
        return OCRPageResult(text="Invoice No: INV-002", confidence=88.0)


class _IntegrationExtractor:
    async def extract(self, request: ExtractionRequest) -> InvoiceExtraction:
        """Return a synthetic extraction that matches stored reference data."""
        return InvoiceExtraction(
            document_type="invoice",
            vendor_name="Fictional Supplies Ltd.",
            invoice_number="INV-002",
            ocr_confidence=request.document.confidence,
        )


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (16, 8), color="white").save(output, format="PNG")
    return output.getvalue()


@pytest.mark.anyio
async def test_process_endpoint_runs_the_complete_dependency_graph(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    repository = SQLiteInvoiceRepository(database_path)
    repository.initialize()
    repository.add_invoice(
        HistoricalInvoice(
            vendor_key="fictional-supplies-ltd",
            invoice_number="INV-002",
        )
    )
    monkeypatch.setenv("VERIDOC_REFERENCE_DATABASE", str(database_path))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("VERIDOC_LLM_MODEL", raising=False)
    app.dependency_overrides[get_ocr_engine] = _IntegrationOCREngine
    app.dependency_overrides[get_structured_extractor] = _IntegrationExtractor
    app.dependency_overrides[get_explanation_service] = lambda: ExplanationService()

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/process",
                files={"file": ("fictional-invoice.png", _png_bytes(), "image/png")},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["extraction"]["vendor_name"] == "Fictional Supplies Ltd."
    assert body["findings"][0]["finding_type"] == "duplicate_invoice_number"
    assert body["explanations"][0]["finding"] == body["findings"][0]
    assert body["verdict"] == {
        "status": "review_required",
        "summary": "1 deterministic verification finding requires review.",
        "finding_count": 1,
        "highest_severity": "high",
    }
    assert repository.list_vendor_invoices("fictional-supplies-ltd") == [
        HistoricalInvoice(
            vendor_key="fictional-supplies-ltd",
            invoice_number="INV-002",
        )
    ]
