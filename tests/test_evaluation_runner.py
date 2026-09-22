"""Tests for deterministic evaluation runner and uncertainty calculations."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from veridoc.evaluation.models import GroundTruthInvoice, GroundTruthLineItem
from veridoc.evaluation.runner import EvaluationRunner, wilson_score_interval
from veridoc.explanation.service import ExplanationService
from veridoc.extraction.models import (
    EvidenceReference,
    InvoiceExtraction,
    InvoiceLineItem,
)
from veridoc.extraction.protocol import ExtractionRequest
from veridoc.ocr.models import OCRPageResult
from veridoc.processing.service import ProcessingService
from veridoc.verification.references import HistoricalInvoice, PurchaseOrder
from veridoc.verification.service import VerificationService


class _FakeOCREngine:
    def recognize(self, image: Image.Image) -> OCRPageResult:
        return OCRPageResult(text="Invoice INV-100 Acme Inc $100.00", confidence=95.0)


class _FakeExtractor:
    async def extract(self, request: ExtractionRequest) -> InvoiceExtraction:
        return InvoiceExtraction(
            document_type="invoice",
            vendor_name="Acme Inc",
            invoice_number="INV-100",
            total=Decimal("100.00"),
            currency="USD",
            line_items=[
                InvoiceLineItem(
                    description="Consulting",
                    quantity=Decimal(1),
                    unit_price=Decimal("100.00"),
                    total_price=Decimal("100.00"),
                    evidence=[EvidenceReference(page_number=1, source="ocr_text")],
                )
            ],
            evidence={
                "vendor_name": [EvidenceReference(page_number=1, source="ocr_text")],
                "invoice_number": [EvidenceReference(page_number=1, source="ocr_text")],
                "total": [EvidenceReference(page_number=1, source="ocr_text")],
                "currency": [EvidenceReference(page_number=1, source="ocr_text")],
            },
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


def test_wilson_score_interval() -> None:
    # Empty total
    assert wilson_score_interval(0, 0) == (0.0, 1.0)

    # 10 successes out of 10
    lower, upper = wilson_score_interval(10, 10)
    assert lower > 0.69
    assert upper == 1.0

    # 0 successes out of 10
    lower, upper = wilson_score_interval(0, 10)
    assert lower == 0.0
    assert upper < 0.31

    # 50 out of 100
    lower, upper = wilson_score_interval(50, 100)
    assert 0.40 < lower < 0.50
    assert 0.50 < upper < 0.60


@pytest.mark.anyio
async def test_evaluation_runner_run(tmp_path: Path) -> None:
    # Create valid synthetic PNG image
    image = Image.new("RGB", (200, 200), color="white")
    buf = BytesIO()
    image.save(buf, format="PNG")
    img_bytes = buf.getvalue()
    img_sha = hashlib.sha256(img_bytes).hexdigest()

    img_path = tmp_path / "invoices" / "inv1.png"
    img_path.parent.mkdir(parents=True, exist_ok=True)
    img_path.write_bytes(img_bytes)

    # Create ground truth
    gt = GroundTruthInvoice(
        invoice_number="INV-100",
        invoice_date=None,
        due_date=None,
        vendor_name="Acme Inc",
        vendor_tax_id=None,
        currency="USD",
        total_amount=Decimal("100.00"),
        subtotal_amount=None,
        tax_amount=None,
        line_items=[
            GroundTruthLineItem(
                description="Consulting",
                quantity=Decimal(1),
                unit_price=Decimal("100.00"),
                total_amount=Decimal("100.00"),
            )
        ],
        expected_finding_types=["insufficient_history"],
        expected_verdict="review_required",
        ocr_transcript="Invoice INV-100 Acme Inc $100.00",
    )
    gt_bytes = gt.model_dump_json(indent=2).encode("utf-8")
    gt_sha = hashlib.sha256(gt_bytes).hexdigest()
    gt_path = tmp_path / "ground_truth" / "inv1.json"
    gt_path.parent.mkdir(parents=True, exist_ok=True)
    gt_path.write_bytes(gt_bytes)

    # Manifest
    manifest_data = {
        "corpus_name": "Synthetic Test Benchmark",
        "description": "Synthetic benchmark for runner testing",
        "documents": [
            {
                "document_id": "doc-001",
                "file_path": "invoices/inv1.png",
                "file_sha256": img_sha,
                "mime_type": "image/png",
                "page_count": 1,
                "license": "synthetic",
                "provenance": "synthetic-test",
                "language": "eng",
                "quality": "clean",
                "layout": "standard",
                "ground_truth_path": "ground_truth/inv1.json",
                "ground_truth_sha256": gt_sha,
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    # Assemble processing service
    ocr_engine = _FakeOCREngine()
    extractor = _FakeExtractor()
    repo = _EmptyRepository()
    verification_service = VerificationService(repo)
    explanation_service = ExplanationService()
    processing_service = ProcessingService(
        ocr_engine, extractor, verification_service, explanation_service
    )

    runner = EvaluationRunner(ocr_engine, processing_service)
    (
        manifest,
        overall_ocr,
        overall_extraction,
        overall_verification,
        overall_explanation,
        overall_performance,
        slice_summaries,
    ) = await runner.run(manifest_path)

    assert manifest.corpus_name == "Synthetic Test Benchmark"
    assert overall_ocr.cer == 0.0
    assert overall_ocr.wer == 0.0
    assert overall_extraction.precision == 1.0
    assert overall_extraction.recall == 1.0
    assert overall_extraction.f1 == 1.0
    assert overall_extraction.grounded_evidence_rate == 1.0
    assert overall_verification.verdict_concordance == 1.0
    assert overall_explanation.total_explanations == 4
    assert overall_explanation.fallback_invocations == 4
    assert overall_performance.request_count == 1
    assert len(slice_summaries) == 4  # language, quality, layout, page_count
    page_count_summary = next(
        summary
        for summary in slice_summaries
        if summary.slice_dimension == "page_count"
    )
    assert page_count_summary.slice_value == "single"
    assert page_count_summary.sample_count == 1
