"""Complete processing service tests."""

from io import BytesIO

import pytest
from PIL import Image

from veridoc.explanation.service import ExplanationService
from veridoc.extraction.models import InvoiceExtraction
from veridoc.extraction.protocol import ExtractionRequest
from veridoc.ingestion.validation import validate_upload
from veridoc.ocr.models import OCRPageResult
from veridoc.processing.service import ProcessingService
from veridoc.verification.references import HistoricalInvoice, PurchaseOrder
from veridoc.verification.service import VerificationService


class _FakeOCREngine:
    def recognize(self, image: Image.Image) -> OCRPageResult:
        assert image.mode == "RGB"
        return OCRPageResult(text="Invoice No: INV-002", confidence=88.0)


class _FakeExtractor:
    async def extract(self, request: ExtractionRequest) -> InvoiceExtraction:
        return InvoiceExtraction(
            document_type="invoice",
            vendor_name="Fictional Supplies Ltd.",
            invoice_number="INV-002",
            ocr_confidence=request.document.confidence,
        )


class _EmptyRepository:
    def list_vendor_invoices(self, vendor_key: str) -> list[HistoricalInvoice]:
        return []

    def find_invoice(
        self, vendor_key: str, invoice_number: str
    ) -> HistoricalInvoice | None:
        return None

    def get_purchase_order(
        self, vendor_key: str, purchase_order_number: str
    ) -> PurchaseOrder | None:
        return None


class _DuplicateRepository(_EmptyRepository):
    def find_invoice(
        self, vendor_key: str, invoice_number: str
    ) -> HistoricalInvoice | None:
        assert vendor_key == "fictional-supplies-ltd"
        assert invoice_number == "INV-002"
        return HistoricalInvoice(
            vendor_key=vendor_key,
            invoice_number=invoice_number,
        )


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (16, 8), color="white").save(output, format="PNG")
    return output.getvalue()


@pytest.mark.anyio
async def test_processing_service_returns_the_complete_typed_result() -> None:
    service = ProcessingService(
        _FakeOCREngine(),
        _FakeExtractor(),
        VerificationService(_EmptyRepository()),
        ExplanationService(),
    )
    upload = validate_upload(
        _png_bytes(),
        filename="fictional-invoice.png",
        declared_content_type="image/png",
    )

    result = await service.process(upload)

    assert result.extraction.invoice_number == "INV-002"
    assert result.verdict.status == "clear"


@pytest.mark.anyio
async def test_processing_service_carries_a_duplicate_finding_to_review() -> None:
    service = ProcessingService(
        _FakeOCREngine(),
        _FakeExtractor(),
        VerificationService(_DuplicateRepository()),
        ExplanationService(),
    )
    upload = validate_upload(
        _png_bytes(),
        filename="fictional-invoice.png",
        declared_content_type="image/png",
    )

    result = await service.process(upload)

    assert result.findings[0].finding_type == "duplicate_invoice_number"
    assert result.explanations[0].finding == result.findings[0]
    assert result.explanations[0].source == "deterministic"
    assert result.verdict.status == "review_required"
