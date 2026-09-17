"""Tests for evaluation decision evaluator and markdown report generator."""

from __future__ import annotations

from veridoc.evaluation.decision import (
    create_evaluation_report,
    evaluate_decision,
    render_markdown_report,
)
from veridoc.evaluation.models import (
    ArtifactIdentityRecord,
    EvaluationThresholds,
    ExplanationMetrics,
    ExtractionMetrics,
    OCRMetrics,
    PerformanceMetrics,
    ProviderIdentityRecord,
    SliceMetricsSummary,
    VerificationMetrics,
)


def _sample_artifacts() -> tuple[ArtifactIdentityRecord, ProviderIdentityRecord]:
    artifact = ArtifactIdentityRecord(
        app_version="0.1.0",
        git_commit="abcdef123456",
        python_version="3.12.0",
        platform="win32",
        lockfile_sha256="1" * 64,
        tesseract_version="5.3.0",
        tessdata_sha256={},
        reference_schema_version=4,
        review_schema_version=4,
    )
    provider = ProviderIdentityRecord(
        model_name="gpt-4o-mini",
        system_prompt_sha256="2" * 64,
        extraction_schema_sha256="3" * 64,
    )
    return artifact, provider


def _passing_metrics() -> tuple[
    OCRMetrics,
    ExtractionMetrics,
    VerificationMetrics,
    ExplanationMetrics,
    PerformanceMetrics,
]:
    ocr = OCRMetrics(
        character_count=1000,
        word_count=200,
        character_errors=10,
        word_errors=5,
        cer=0.01,
        wer=0.025,
    )
    ext = ExtractionMetrics(
        field_count=100,
        exact_match_count=98,
        precision=0.98,
        recall=0.98,
        f1=0.98,
        line_item_f1=0.95,
        grounded_evidence_rate=0.99,
    )
    ver = VerificationMetrics(
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
    )
    exp = ExplanationMetrics(
        total_explanations=10,
        guardrail_passes=10,
        guardrail_rejections=0,
        guardrail_pass_rate=1.0,
        numerical_contradictions=0,
        fallback_invocations=0,
    )
    perf = PerformanceMetrics(
        request_count=20,
        p50_latency_seconds=1.0,
        p95_latency_seconds=2.5,
        p99_latency_seconds=3.0,
        requests_per_second=5.0,
        timeout_failures=0,
        concurrency_rejections=0,
    )
    return ocr, ext, ver, exp, perf


def test_evaluate_decision_go() -> None:
    thresholds = EvaluationThresholds()
    ocr, ext, ver, exp, perf = _passing_metrics()
    slices = [
        SliceMetricsSummary(
            slice_dimension="language",
            slice_value="eng",
            sample_count=20,
            sufficient_sample_size=True,
            ocr_cer=0.01,
            ocr_wer=0.02,
            extraction_f1=0.98,
            verification_fnr=0.0,
            verdict_accuracy=1.0,
        )
    ]
    results, decision, rationale, _limitations = evaluate_decision(
        thresholds, ocr, ext, ver, exp, perf, slices
    )
    assert decision == "go"
    assert "fully satisfied" in rationale
    assert len(results) == 8
    assert all(r.passed for r in results)


def test_evaluate_decision_no_go_on_verification_fnr() -> None:
    thresholds = EvaluationThresholds()
    ocr, ext, ver, exp, perf = _passing_metrics()
    # Breach hard constraint: verification false negative rate > 0
    bad_ver = ver.model_copy(update={"fnr": 0.05, "false_negatives": 1})
    slices = [
        SliceMetricsSummary(
            slice_dimension="language",
            slice_value="eng",
            sample_count=20,
            sufficient_sample_size=True,
            verification_fnr=0.05,
            verdict_accuracy=0.95,
        )
    ]
    results, decision, rationale, _ = evaluate_decision(
        thresholds, ocr, ext, bad_ver, exp, perf, slices
    )
    assert decision == "no_go"
    assert "Critical threshold failures" in rationale
    assert any(
        r.metric_name == "max_verification_fnr" and not r.passed for r in results
    )


def test_evaluate_decision_conditional_go_on_minor_or_undersampled() -> None:
    thresholds = EvaluationThresholds()
    ocr, ext, ver, exp, perf = _passing_metrics()
    # Undersampled slice
    slices = [
        SliceMetricsSummary(
            slice_dimension="language",
            slice_value="ara",
            sample_count=2,  # < 10
            sufficient_sample_size=False,
            verification_fnr=0.0,
            verdict_accuracy=1.0,
        )
    ]
    _results, decision, rationale, limitations = evaluate_decision(
        thresholds, ocr, ext, ver, exp, perf, slices
    )
    assert decision == "conditional_go"
    assert "Approved conditionally" in rationale
    assert len(limitations) == 1
    assert "Under-sampled slices" in limitations[0]


def test_create_and_render_report() -> None:
    artifact, provider = _sample_artifacts()
    thresholds = EvaluationThresholds()
    ocr, ext, ver, exp, perf = _passing_metrics()
    slices = [
        SliceMetricsSummary(
            slice_dimension="language",
            slice_value="eng",
            sample_count=20,
            sufficient_sample_size=True,
            ocr_cer=0.01,
            ocr_wer=0.02,
            extraction_f1=0.98,
            verification_fnr=0.0,
            verdict_accuracy=1.0,
        )
    ]
    report = create_evaluation_report(
        evaluation_id="eval-test-001",
        manifest_name="test-manifest",
        manifest_version="1.0",
        total_documents=20,
        artifact_identity=artifact,
        provider_identity=provider,
        thresholds=thresholds,
        overall_ocr=ocr,
        overall_extraction=ext,
        overall_verification=ver,
        overall_explanation=exp,
        overall_performance=perf,
        slice_summaries=slices,
        expiry_date="2026-12-31",
    )
    assert report.decision == "go"
    markdown = render_markdown_report(report)
    assert "# Veridoc Evaluation and Production-Readiness Report" in markdown
    assert "**GO (Production-Ready)**" in markdown
    assert "eval-test-001" in markdown
    assert "2026-12-31" in markdown
