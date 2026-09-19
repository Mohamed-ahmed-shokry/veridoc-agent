"""Complete processing graph composition tests."""

from io import BytesIO

import pytest
from PIL import Image

from veridoc.explanation.service import ExplanationService
from veridoc.extraction.models import InvoiceExtraction
from veridoc.extraction.protocol import ExtractionRequest
from veridoc.ingestion.validation import validate_upload
from veridoc.ocr.models import OCRPageResult
from veridoc.processing.graph import build_processing_graph
from veridoc.verification.references import HistoricalInvoice, PurchaseOrder
from veridoc.verification.service import VerificationService


class _FakeOCREngine:
    def recognize(self, image: Image.Image) -> OCRPageResult:
        assert image.mode == "RGB"
        return OCRPageResult(text="Invoice No: INV-001", confidence=93.0)


class _FakeExtractor:
    async def extract(self, request: ExtractionRequest) -> InvoiceExtraction:
        return InvoiceExtraction(
            document_type="invoice",
            invoice_number="INV-001",
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


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (16, 8), color="white").save(output, format="PNG")
    return output.getvalue()


@pytest.mark.anyio
async def test_processing_graph_runs_every_phase_to_a_typed_result() -> None:
    graph = build_processing_graph(
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

    state = await graph.ainvoke({"upload": upload})

    assert state["ocr"].document.confidence == 93.0
    assert state["extraction"].invoice_number == "INV-001"
    assert state["verification"].findings == []
    assert state["explanations"].explanations == []
    assert state["result"].verdict.status == "clear"


@pytest.mark.anyio
async def test_processing_graph_attaches_vendor_resolution(tmp_path) -> None:
    from veridoc.persistence.sqlite import SQLiteVendorRepository
    from veridoc.vendors.models import VendorEntity

    repo = SQLiteVendorRepository(tmp_path / "reference.sqlite")
    repo.initialize()
    repo.add_vendor(
        VendorEntity(
            vendor_id="vnd_001",
            legal_name="Acme Corp",
            canonical_key="acme-corp",
            status="active",
        )
    )

    class _VendorExtractor:
        async def extract(self, request: ExtractionRequest) -> InvoiceExtraction:
            return InvoiceExtraction(
                document_type="invoice",
                invoice_number="INV-001",
                vendor_name="Acme Corp",
            )

    graph = build_processing_graph(
        _FakeOCREngine(),
        _VendorExtractor(),
        VerificationService(repo),
        ExplanationService(),
    )
    upload = validate_upload(
        _png_bytes(),
        filename="fictional-invoice.png",
        declared_content_type="image/png",
    )

    state = await graph.ainvoke({"upload": upload})
    assert state["result"].vendor_resolution is not None
    assert state["result"].vendor_resolution.resolved_vendor_id == "vnd_001"
    assert state["result"].vendor_resolution.confidence == "exact_alias"
