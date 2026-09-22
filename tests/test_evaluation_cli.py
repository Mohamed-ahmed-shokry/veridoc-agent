"""Tests for veridoc-evaluate command-line interface."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from veridoc.evaluation.cli import main, parse_args
from veridoc.evaluation.manifest import load_corpus_manifest
from veridoc.evaluation.models import (
    ArtifactIdentityRecord,
    EvaluationReport,
    EvaluationThresholds,
    ExplanationMetrics,
    ExtractionMetrics,
    OCRMetrics,
    PerformanceMetrics,
    ProviderIdentityRecord,
    VerificationMetrics,
)
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
        return OCRPageResult(text="Invoice INV-2026-0001", confidence=95.0)


class _FakeExtractor:
    async def extract(self, request: ExtractionRequest) -> InvoiceExtraction:
        return InvoiceExtraction(
            document_type="invoice",
            vendor_name="Acme Industrial Supplies",
            invoice_number="INV-2026-0001",
            total=Decimal("110.00"),
            currency="USD",
            line_items=[
                InvoiceLineItem(
                    description="Consulting Service",
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


def _make_fake_service() -> tuple[_FakeOCREngine, ProcessingService]:
    engine = _FakeOCREngine()
    extractor = _FakeExtractor()
    repo = _EmptyRepository()
    service = ProcessingService(
        engine,
        extractor,
        VerificationService(repo),
        ExplanationService(),
    )
    return engine, service


def test_parse_args() -> None:
    args = parse_args(
        [
            "--manifest",
            "tests/fixtures/corpus/manifest.json",
            "--output-json",
            "report.json",
            "--output-markdown",
            "report.md",
            "--fail-on-no-go",
        ]
    )
    assert args.manifest == Path("tests/fixtures/corpus/manifest.json")
    assert args.output_json == Path("report.json")
    assert args.output_markdown == Path("report.md")
    assert args.fail_on_no_go is True
    assert args.no_verify_integrity is False


def test_cli_main_success(tmp_path: Path) -> None:
    manifest_path = Path("tests/fixtures/corpus/manifest.json").resolve()
    assert manifest_path.is_file(), "Benchmark corpus manifest must exist"

    out_json = tmp_path / "report.json"
    out_md = tmp_path / "report.md"

    engine, service = _make_fake_service()

    code = main(
        [
            "--manifest",
            str(manifest_path),
            "--output-json",
            str(out_json),
            "--output-markdown",
            str(out_md),
            "--evaluation-id",
            "test-eval-run-001",
        ],
        ocr_engine=engine,
        processing_service=service,
    )

    assert code == 0
    assert out_json.is_file()
    assert out_md.is_file()

    # Verify JSON deserializes cleanly
    report = EvaluationReport.model_validate_json(out_json.read_text(encoding="utf-8"))
    assert report.evaluation_id == "test-eval-run-001"
    manifest, _ = load_corpus_manifest(manifest_path, verify_integrity=False)
    assert report.total_documents == len(manifest.documents)


def test_cli_main_invalid_manifest(tmp_path: Path) -> None:
    code = main(["--manifest", str(tmp_path / "missing-manifest.json")])
    assert code == 2


def test_cli_main_fail_on_no_go(tmp_path: Path) -> None:
    manifest_path = Path("tests/fixtures/corpus/manifest.json").resolve()
    engine, service = _make_fake_service()

    # Mock evaluate_decision to return "no_go"
    with patch("veridoc.evaluation.cli.create_evaluation_report") as mock_create:
        mock_report = EvaluationReport(
            evaluation_id="eval-mock-no-go",
            manifest_name="test",
            manifest_version="1.0",
            total_documents=1,
            artifact_identity=capture_artifact_from_test(),
            provider_identity=capture_provider_from_test(),
            thresholds=EvaluationThresholds(),
            threshold_results=[],
            slice_summaries=[],
            overall_ocr=OCRMetrics(
                character_count=1,
                word_count=1,
                character_errors=0,
                word_errors=0,
                cer=0.0,
                wer=0.0,
            ),
            overall_extraction=ExtractionMetrics(
                field_count=1,
                exact_match_count=1,
                precision=1.0,
                recall=1.0,
                f1=1.0,
                line_item_f1=1.0,
                grounded_evidence_rate=1.0,
            ),
            overall_verification=VerificationMetrics(
                rules_evaluated=1,
                true_positives=1,
                true_negatives=0,
                false_positives=0,
                false_negatives=0,
                tpr=1.0,
                tnr=1.0,
                fpr=0.0,
                fnr=0.0,
                verdict_concordance=1.0,
            ),
            overall_explanation=ExplanationMetrics(
                total_explanations=0,
                guardrail_passes=0,
                guardrail_rejections=0,
                guardrail_pass_rate=1.0,
                numerical_contradictions=0,
                fallback_invocations=0,
            ),
            overall_performance=PerformanceMetrics(
                request_count=1,
                p50_latency_seconds=1.0,
                p95_latency_seconds=1.0,
                p99_latency_seconds=1.0,
                requests_per_second=1.0,
                timeout_failures=0,
                concurrency_rejections=0,
            ),
            decision="no_go",
            decision_rationale="Simulated critical failure.",
        )
        mock_create.return_value = mock_report

        code = main(
            [
                "--manifest",
                str(manifest_path),
                "--fail-on-no-go",
            ],
            ocr_engine=engine,
            processing_service=service,
        )
        assert code == 1


def capture_artifact_from_test() -> ArtifactIdentityRecord:
    return ArtifactIdentityRecord(
        app_version="0.1.0",
        git_commit="a" * 40,
        python_version="3.12.0",
        platform="win32",
        lockfile_sha256="1" * 64,
        tesseract_version="5.3.0",
        tessdata_sha256={},
        reference_schema_version=4,
        review_schema_version=4,
    )


def capture_provider_from_test() -> ProviderIdentityRecord:
    return ProviderIdentityRecord(
        model_name="test-model",
        system_prompt_sha256="2" * 64,
        extraction_schema_sha256="3" * 64,
    )
