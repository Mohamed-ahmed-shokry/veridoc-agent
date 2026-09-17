"""Tests for Phase 11 evaluation domain models and schemas."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from veridoc.evaluation.models import (
    ArtifactIdentityRecord,
    CorpusDocument,
    CorpusManifest,
    EvaluationReport,
    EvaluationThresholds,
    ExplanationMetrics,
    ExtractionMetrics,
    GroundTruthInvoice,
    GroundTruthLineItem,
    OCRMetrics,
    PerformanceMetrics,
    ProviderIdentityRecord,
    ThresholdEvaluationResult,
    VerificationMetrics,
)


def test_ground_truth_invoice_valid() -> None:
    gt = GroundTruthInvoice(
        invoice_number="INV-2026-001",
        invoice_date="2026-03-01",
        due_date="2026-03-31",
        vendor_name="Acme Corp",
        vendor_tax_id="123456789",
        currency="USD",
        total_amount=Decimal("115.00"),
        subtotal_amount=Decimal("100.00"),
        tax_amount=Decimal("15.00"),
        line_items=[
            GroundTruthLineItem(
                description="Widget A",
                quantity=Decimal(2),
                unit_price=Decimal("50.00"),
                total_amount=Decimal("100.00"),
            )
        ],
        expected_finding_types=[],
        expected_verdict="clear",
        ocr_transcript="Invoice INV-2026-001 Total $115.00",
    )
    assert gt.invoice_number == "INV-2026-001"
    assert gt.total_amount == Decimal("115.00")
    assert len(gt.line_items) == 1
    assert gt.expected_verdict == "clear"


def test_corpus_document_validation() -> None:
    valid_sha = "a" * 64
    doc = CorpusDocument(
        document_id="doc-001",
        file_path="invoices/doc1.pdf",
        file_sha256=valid_sha,
        mime_type="application/pdf",
        page_count=2,
        license="synthetic",
        provenance="synthetic-generator-v1",
        language="eng",
        quality="clean",
        layout="standard",
        ground_truth_path="ground_truth/doc1.json",
        ground_truth_sha256=valid_sha,
    )
    assert doc.document_id == "doc-001"
    assert doc.language == "eng"
    assert doc.page_count == 2

    # Reject invalid sha256
    with pytest.raises(ValidationError):
        CorpusDocument(
            document_id="doc-002",
            file_path="invoices/doc2.pdf",
            file_sha256="not-a-valid-sha",
            mime_type="application/pdf",
            page_count=1,
            license="synthetic",
            provenance="test",
            language="eng",
            quality="clean",
            layout="standard",
            ground_truth_path="gt.json",
            ground_truth_sha256=valid_sha,
        )

    # Reject invalid extra fields
    with pytest.raises(ValidationError):
        CorpusDocument(
            document_id="doc-003",
            file_path="invoices/doc3.pdf",
            file_sha256=valid_sha,
            mime_type="application/pdf",
            page_count=1,
            license="synthetic",
            provenance="test",
            language="eng",
            quality="clean",
            layout="standard",
            ground_truth_path="gt.json",
            ground_truth_sha256=valid_sha,
            extra_field="disallowed",  # type: ignore[call-arg]
        )


def test_corpus_manifest_validation() -> None:
    valid_sha = "b" * 64
    doc = CorpusDocument(
        document_id="doc-001",
        file_path="invoices/doc1.pdf",
        file_sha256=valid_sha,
        mime_type="application/pdf",
        page_count=1,
        license="synthetic",
        provenance="generator",
        language="ara",
        quality="noisy",
        layout="dense",
        ground_truth_path="gt/doc1.json",
        ground_truth_sha256=valid_sha,
    )
    manifest = CorpusManifest(
        corpus_name="Test Corpus",
        description="A test corpus for verification",
        documents=[doc],
    )
    assert manifest.corpus_name == "Test Corpus"
    assert len(manifest.documents) == 1

    # Manifest requires at least one document
    with pytest.raises(ValidationError):
        CorpusManifest(
            corpus_name="Empty Corpus",
            description="Empty",
            documents=[],
        )


def test_evaluation_thresholds_defaults() -> None:
    thresholds = EvaluationThresholds()
    assert thresholds.max_ocr_cer == 0.05
    assert thresholds.max_ocr_wer == 0.15
    assert thresholds.min_extraction_f1 == 0.90
    assert thresholds.max_verification_fnr == 0.00
    assert thresholds.min_verdict_accuracy == 0.95


def test_evaluation_report_schema() -> None:
    artifact_id = ArtifactIdentityRecord(
        app_version="0.1.0",
        git_commit="abcdef123456",
        python_version="3.12.12",
        platform="win32",
        lockfile_sha256="c" * 64,
        tesseract_version="5.3.0",
        tessdata_sha256={"eng": "d" * 64},
        reference_schema_version=4,
        review_schema_version=4,
    )
    provider_id = ProviderIdentityRecord(
        model_name="gpt-4o-mini",
        system_prompt_sha256="e" * 64,
        extraction_schema_sha256="f" * 64,
    )
    report = EvaluationReport(
        evaluation_id="eval-20260917-001",
        manifest_name="synthetic-benchmark-v1",
        manifest_version="1.0",
        total_documents=20,
        artifact_identity=artifact_id,
        provider_identity=provider_id,
        thresholds=EvaluationThresholds(),
        threshold_results=[
            ThresholdEvaluationResult(
                metric_name="max_ocr_cer",
                observed_value=0.02,
                threshold_value=0.05,
                comparator="<=",
                passed=True,
            )
        ],
        slice_summaries=[],
        overall_ocr=OCRMetrics(
            character_count=1000,
            word_count=200,
            character_errors=20,
            word_errors=10,
            cer=0.02,
            wer=0.05,
        ),
        overall_extraction=ExtractionMetrics(
            field_count=100,
            exact_match_count=95,
            precision=0.96,
            recall=0.95,
            f1=0.955,
            line_item_f1=0.92,
            grounded_evidence_rate=0.98,
        ),
        overall_verification=VerificationMetrics(
            rules_evaluated=50,
            true_positives=10,
            true_negatives=40,
            false_positives=0,
            false_negatives=0,
            tpr=1.0,
            tnr=1.0,
            fpr=0.0,
            fnr=0.0,
            verdict_concordance=1.0,
        ),
        overall_explanation=ExplanationMetrics(
            total_explanations=10,
            guardrail_passes=10,
            guardrail_rejections=0,
            guardrail_pass_rate=1.0,
            numerical_contradictions=0,
            fallback_invocations=0,
        ),
        overall_performance=PerformanceMetrics(
            request_count=20,
            p50_latency_seconds=1.2,
            p95_latency_seconds=2.8,
            p99_latency_seconds=3.5,
            requests_per_second=2.5,
            timeout_failures=0,
            concurrency_rejections=0,
        ),
        decision="go",
        decision_rationale="All acceptance thresholds satisfied with high confidence.",
    )
    assert report.decision == "go"
    assert report.total_documents == 20
    assert report.overall_ocr.cer == 0.02
