"""Complete review case-creation integration through the real processing graph.

Unlike test_review_case_creation_api.py (which fakes the whole
ProcessingService to test the route's own contract in isolation), this
module retains the real ProcessingService and processing graph, faking only
the external OCR engine, structured extractor, and explanation provider —
mirroring how test_processing_integration.py exercises /process end to end.
"""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path

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
from veridoc.review.api import (
    CSRF_HEADER_NAME,
    IDEMPOTENCY_KEY_HEADER,
    get_review_actor_directory,
    get_review_origin_settings,
    get_review_repository,
)
from veridoc.review.config import (
    ReviewActor,
    ReviewActorDirectory,
    ReviewOriginSettings,
)
from veridoc.review.persistence.sqlite import SQLiteReviewRepository
from veridoc.verification.references import HistoricalInvoice

_REVIEWER_SECRET = "reviewer-secret-value"
_ORIGIN = "https://review.example"


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


def _digest(secret: str) -> str:
    return sha256(secret.encode("utf-8")).hexdigest()


def _directory() -> ReviewActorDirectory:
    return ReviewActorDirectory(
        _actors_by_id={
            "reviewer-1": ReviewActor(
                actor_id="reviewer-1",
                role="reviewer",
                secret_digest=_digest(_REVIEWER_SECRET),
            )
        }
    )


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


@pytest.mark.anyio
async def test_create_review_case_runs_the_complete_dependency_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference_database = tmp_path / "reference-data.sqlite"
    reference_repository = SQLiteInvoiceRepository(reference_database)
    reference_repository.initialize()
    reference_repository.add_invoice(
        HistoricalInvoice(
            vendor_key="fictional-supplies-ltd",
            invoice_number="INV-002",
        )
    )
    monkeypatch.setenv("VERIDOC_REFERENCE_DATABASE", str(reference_database))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("VERIDOC_LLM_MODEL", raising=False)

    review_repository = SQLiteReviewRepository(tmp_path / "review.sqlite")
    review_repository.initialize()
    app.dependency_overrides[get_ocr_engine] = _IntegrationOCREngine
    app.dependency_overrides[get_structured_extractor] = _IntegrationExtractor
    app.dependency_overrides[get_explanation_service] = lambda: ExplanationService()
    app.dependency_overrides[get_review_repository] = lambda: review_repository
    app.dependency_overrides[get_review_actor_directory] = _directory
    app.dependency_overrides[get_review_origin_settings] = lambda: ReviewOriginSettings(
        origin=_ORIGIN
    )

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            login = await client.post(
                "/review/session",
                headers={
                    "Authorization": f"Bearer {_REVIEWER_SECRET}",
                    "Origin": _ORIGIN,
                },
            )
            client.cookies.set(
                "veridoc_review_session", login.cookies["veridoc_review_session"]
            )
            client.cookies.set(
                "veridoc_review_csrf", login.cookies["veridoc_review_csrf"]
            )
            response = await client.post(
                "/review/cases",
                headers={
                    "Origin": _ORIGIN,
                    CSRF_HEADER_NAME: login.cookies["veridoc_review_csrf"],
                    IDEMPOTENCY_KEY_HEADER: "integration-key-1",
                },
                files={"file": ("fictional-invoice.png", _png_bytes(), "image/png")},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    result = body["snapshot"]["result"]
    assert result["extraction"]["vendor_name"] == "Fictional Supplies Ltd."
    assert result["findings"][0]["finding_type"] == "duplicate_invoice_number"
    assert result["explanations"][0]["finding"] == result["findings"][0]
    assert result["verdict"] == {
        "status": "review_required",
        "summary": "1 deterministic verification finding requires review.",
        "finding_count": 1,
        "highest_severity": "high",
    }
    assert body["status"] == "unassigned"
    assert body["creator_actor_id"] == "reviewer-1"

    persisted = review_repository.get_case(body["case_id"])
    assert persisted is not None
    assert persisted.snapshot.result.extraction.vendor_name == "Fictional Supplies Ltd."
    assert reference_repository.list_vendor_invoices("fictional-supplies-ltd") == [
        HistoricalInvoice(
            vendor_key="fictional-supplies-ltd",
            invoice_number="INV-002",
        )
    ]
