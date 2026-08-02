"""In-process tests for the complete invoice-processing endpoint."""

from __future__ import annotations

from io import BytesIO

import httpx
import pytest
from PIL import Image

from veridoc.app import app, get_processing_service
from veridoc.explanation.models import FindingExplanation
from veridoc.extraction.models import EvidenceReference, InvoiceExtraction
from veridoc.persistence.protocol import ReferenceDataUnavailableError
from veridoc.processing.models import ProcessingResult, ProcessingVerdict
from veridoc.processing.service import ProcessingError
from veridoc.verification.models import VerificationFinding


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (12, 8), color="white").save(output, format="PNG")
    return output.getvalue()


def _result() -> ProcessingResult:
    finding = VerificationFinding(
        finding_type="duplicate_invoice_number",
        severity="high",
        explanation="The invoice number already exists for this vendor.",
        comparison_source="invoice_register",
        deterministic_rule="invoice_number must be unique within vendor history",
        observed_value="INV-001",
    )
    return ProcessingResult(
        extraction=InvoiceExtraction(
            document_type="invoice",
            invoice_number="INV-001",
            evidence={
                "invoice_number": [
                    EvidenceReference(
                        page_number=1,
                        source="ocr_text",
                        text_span="Invoice No: INV-001",
                    )
                ]
            },
        ),
        findings=[finding],
        explanations=[
            FindingExplanation(
                finding=finding,
                narrative="Review the existing invoice record before proceeding.",
                numerical_context="Observed value: INV-001.",
                source="deterministic",
            )
        ],
        verdict=ProcessingVerdict(
            status="review_required",
            summary="1 deterministic verification finding requires review.",
            finding_count=1,
            highest_severity="high",
        ),
    )


class _FakeProcessingService:
    def __init__(self) -> None:
        self.uploads = []

    async def process(self, upload):
        self.uploads.append(upload)
        return _result()


async def _post_file(service: _FakeProcessingService) -> httpx.Response:
    app.dependency_overrides[get_processing_service] = lambda: service
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.post(
                "/process",
                files={"file": ("fictional-invoice.png", _png_bytes(), "image/png")},
            )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_process_endpoint_returns_evidence_findings_explanations_and_verdict() -> (
    None
):
    service = _FakeProcessingService()

    response = await _post_file(service)

    assert response.status_code == 200
    body = response.json()
    assert service.uploads[0].filename == "fictional-invoice.png"
    assert body["extraction"]["evidence"]["invoice_number"][0]["page_number"] == 1
    assert body["findings"][0]["finding_type"] == "duplicate_invoice_number"
    assert body["explanations"][0]["source"] == "deterministic"
    assert body["verdict"]["status"] == "review_required"


@pytest.mark.anyio
async def test_process_endpoint_reports_missing_extraction_configuration_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("VERIDOC_LLM_MODEL", raising=False)
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

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "extraction_unavailable"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("exception", "status_code", "code"),
    [
        (ProcessingError(), 422, "processing_failed"),
        (ReferenceDataUnavailableError(), 503, "reference_data_unavailable"),
    ],
)
async def test_process_endpoint_returns_safe_orchestration_errors(
    exception: RuntimeError, status_code: int, code: str
) -> None:
    def raise_error():
        raise exception

    app.dependency_overrides[get_processing_service] = raise_error
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

    assert response.status_code == status_code
    assert response.json()["detail"]["code"] == code
