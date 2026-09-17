"""Evaluation decision formulation and auditable report generation."""

from __future__ import annotations

from typing import Final

from veridoc.evaluation.models import (
    ArtifactIdentityRecord,
    DecisionOutcome,
    EvaluationReport,
    EvaluationThresholds,
    ExplanationMetrics,
    ExtractionMetrics,
    OCRMetrics,
    PerformanceMetrics,
    ProviderIdentityRecord,
    SliceMetricsSummary,
    ThresholdEvaluationResult,
    VerificationMetrics,
)

_CRITICAL_METRIC_NAMES: Final[frozenset[str]] = frozenset(
    {
        "max_verification_fnr",
        "min_verdict_accuracy",
        "min_extraction_f1",
        "min_guardrail_pass_rate",
    }
)


def evaluate_decision(
    thresholds: EvaluationThresholds,
    overall_ocr: OCRMetrics,
    overall_extraction: ExtractionMetrics,
    overall_verification: VerificationMetrics,
    overall_explanation: ExplanationMetrics,
    overall_performance: PerformanceMetrics,
    slice_summaries: list[SliceMetricsSummary],
    drift_warnings: list[str] | None = None,
) -> tuple[list[ThresholdEvaluationResult], DecisionOutcome, str, list[str]]:
    """Evaluate observed metrics against thresholds and derive a go/conditional_go/no_go decision."""
    results: list[ThresholdEvaluationResult] = []
    limitations: list[str] = []
    if drift_warnings:
        limitations.extend([f"Drift warning: {w}" for w in drift_warnings])

    # 1. max_ocr_cer
    passed_cer = overall_ocr.cer <= thresholds.max_ocr_cer
    results.append(
        ThresholdEvaluationResult(
            metric_name="max_ocr_cer",
            observed_value=overall_ocr.cer,
            threshold_value=thresholds.max_ocr_cer,
            comparator="<=",
            passed=passed_cer,
        )
    )

    # 2. max_ocr_wer
    passed_wer = overall_ocr.wer <= thresholds.max_ocr_wer
    results.append(
        ThresholdEvaluationResult(
            metric_name="max_ocr_wer",
            observed_value=overall_ocr.wer,
            threshold_value=thresholds.max_ocr_wer,
            comparator="<=",
            passed=passed_wer,
        )
    )

    # 3. min_extraction_f1
    passed_ext_f1 = overall_extraction.f1 >= thresholds.min_extraction_f1
    results.append(
        ThresholdEvaluationResult(
            metric_name="min_extraction_f1",
            observed_value=overall_extraction.f1,
            threshold_value=thresholds.min_extraction_f1,
            comparator=">=",
            passed=passed_ext_f1,
        )
    )

    # 4. min_line_item_f1
    passed_li_f1 = overall_extraction.line_item_f1 >= thresholds.min_line_item_f1
    results.append(
        ThresholdEvaluationResult(
            metric_name="min_line_item_f1",
            observed_value=overall_extraction.line_item_f1,
            threshold_value=thresholds.min_line_item_f1,
            comparator=">=",
            passed=passed_li_f1,
        )
    )

    # 5. max_verification_fnr (hard safety constraint)
    passed_fnr = overall_verification.fnr <= thresholds.max_verification_fnr
    results.append(
        ThresholdEvaluationResult(
            metric_name="max_verification_fnr",
            observed_value=overall_verification.fnr,
            threshold_value=thresholds.max_verification_fnr,
            comparator="<=",
            passed=passed_fnr,
        )
    )

    # 6. min_verdict_accuracy
    passed_verdict = (
        overall_verification.verdict_concordance >= thresholds.min_verdict_accuracy
    )
    results.append(
        ThresholdEvaluationResult(
            metric_name="min_verdict_accuracy",
            observed_value=overall_verification.verdict_concordance,
            threshold_value=thresholds.min_verdict_accuracy,
            comparator=">=",
            passed=passed_verdict,
        )
    )

    # 7. min_guardrail_pass_rate
    passed_guardrails = (
        overall_explanation.guardrail_pass_rate >= thresholds.min_guardrail_pass_rate
    )
    results.append(
        ThresholdEvaluationResult(
            metric_name="min_guardrail_pass_rate",
            observed_value=overall_explanation.guardrail_pass_rate,
            threshold_value=thresholds.min_guardrail_pass_rate,
            comparator=">=",
            passed=passed_guardrails,
        )
    )

    # 8. max_p95_latency_seconds
    passed_p95 = (
        overall_performance.p95_latency_seconds <= thresholds.max_p95_latency_seconds
    )
    results.append(
        ThresholdEvaluationResult(
            metric_name="max_p95_latency_seconds",
            observed_value=overall_performance.p95_latency_seconds,
            threshold_value=thresholds.max_p95_latency_seconds,
            comparator="<=",
            passed=passed_p95,
        )
    )

    # Slice evaluation
    slice_failures: list[str] = []
    insufficient_slices: list[str] = []

    for s in slice_summaries:
        if not s.sufficient_sample_size:
            insufficient_slices.append(
                f"{s.slice_dimension}={s.slice_value} (sample_count={s.sample_count} < {thresholds.min_slice_sample_count})"
            )
        else:
            if (
                s.verification_fnr is not None
                and s.verification_fnr > thresholds.max_verification_fnr
            ):
                slice_failures.append(
                    f"Slice {s.slice_dimension}={s.slice_value} failed max_verification_fnr ({s.verification_fnr} > {thresholds.max_verification_fnr})"
                )
            if (
                s.verdict_accuracy is not None
                and s.verdict_accuracy < thresholds.min_verdict_accuracy
            ):
                slice_failures.append(
                    f"Slice {s.slice_dimension}={s.slice_value} failed min_verdict_accuracy ({s.verdict_accuracy} < {thresholds.min_verdict_accuracy})"
                )

    if insufficient_slices:
        limitations.append(
            f"Under-sampled slices requiring sample expansion: {', '.join(insufficient_slices)}"
        )

    # Determine DecisionOutcome
    critical_failed = [
        r.metric_name
        for r in results
        if not r.passed and r.metric_name in _CRITICAL_METRIC_NAMES
    ]
    non_critical_failed = [
        r.metric_name
        for r in results
        if not r.passed and r.metric_name not in _CRITICAL_METRIC_NAMES
    ]

    decision: DecisionOutcome
    rationale: str

    if critical_failed or slice_failures:
        decision = "no_go"
        reasons = []
        if critical_failed:
            reasons.append(f"Critical threshold failures: {', '.join(critical_failed)}")
        if slice_failures:
            reasons.append(f"Slice threshold failures: {', '.join(slice_failures)}")
        rationale = "; ".join(reasons) + "."
    elif non_critical_failed or insufficient_slices or drift_warnings:
        decision = "conditional_go"
        conditions = []
        if non_critical_failed:
            conditions.append(
                f"Non-critical threshold breaches: {', '.join(non_critical_failed)}"
            )
        if insufficient_slices:
            conditions.append("Certain data slices have insufficient sample size")
        if drift_warnings:
            conditions.append("Upstream/runtime drift detected")
        rationale = f"Approved conditionally. Conditions to remediate before general availability: {'; '.join(conditions)}."
    else:
        decision = "go"
        rationale = "All preregistered acceptance thresholds and slice requirements are fully satisfied."

    return results, decision, rationale, limitations


def create_evaluation_report(
    evaluation_id: str,
    manifest_name: str,
    manifest_version: str,
    total_documents: int,
    artifact_identity: ArtifactIdentityRecord,
    provider_identity: ProviderIdentityRecord,
    thresholds: EvaluationThresholds,
    overall_ocr: OCRMetrics,
    overall_extraction: ExtractionMetrics,
    overall_verification: VerificationMetrics,
    overall_explanation: ExplanationMetrics,
    overall_performance: PerformanceMetrics,
    slice_summaries: list[SliceMetricsSummary],
    drift_warnings: list[str] | None = None,
    expiry_date: str | None = None,
) -> EvaluationReport:
    """Construct an EvaluationReport from evaluated run metrics and thresholds."""
    results, decision, rationale, limitations = evaluate_decision(
        thresholds=thresholds,
        overall_ocr=overall_ocr,
        overall_extraction=overall_extraction,
        overall_verification=overall_verification,
        overall_explanation=overall_explanation,
        overall_performance=overall_performance,
        slice_summaries=slice_summaries,
        drift_warnings=drift_warnings,
    )

    return EvaluationReport(
        evaluation_id=evaluation_id,
        manifest_name=manifest_name,
        manifest_version=manifest_version,
        total_documents=total_documents,
        artifact_identity=artifact_identity,
        provider_identity=provider_identity,
        thresholds=thresholds,
        threshold_results=results,
        slice_summaries=slice_summaries,
        overall_ocr=overall_ocr,
        overall_extraction=overall_extraction,
        overall_verification=overall_verification,
        overall_explanation=overall_explanation,
        overall_performance=overall_performance,
        decision=decision,
        decision_rationale=rationale,
        limitations=limitations,
        exceptions=[],
        expiry_date=expiry_date,
    )


def render_markdown_report(report: EvaluationReport) -> str:
    """Render an auditable, human-readable Markdown evaluation and decision report."""
    badge = {
        "go": "**GO (Production-Ready)**",
        "conditional_go": "**CONDITIONAL GO (Remediation Required)**",
        "no_go": "**NO-GO (Deployment Blocked)**",
    }[report.decision]

    lines = [
        f"# Veridoc Evaluation and Production-Readiness Report: `{report.evaluation_id}`",
        "",
        f"## Decision: {badge}",
        "",
        f"> **Decision Rationale**: {report.decision_rationale}",
        "",
        "### Artifact & Provider Identity",
        "",
        f"- **Application Version**: `{report.artifact_identity.app_version}`",
        f"- **Git Commit**: `{report.artifact_identity.git_commit}`",
        f"- **Python Version**: `{report.artifact_identity.python_version}` (`{report.artifact_identity.platform}`)",
        f"- **Lockfile SHA-256**: `{report.artifact_identity.lockfile_sha256[:16]}...`",
        f"- **Tesseract Version**: `{report.artifact_identity.tesseract_version}`",
        f"- **Reference DB Schema Version**: `{report.artifact_identity.reference_schema_version}`",
        f"- **Review DB Schema Version**: `{report.artifact_identity.review_schema_version}`",
        f"- **Model**: `{report.provider_identity.model_name}`",
        f"- **Corpus Manifest**: `{report.manifest_name}` (version `{report.manifest_version}`, `{report.total_documents}` documents)",
        "",
        "### Preregistered Acceptance Thresholds",
        "",
        "| Metric | Comparator | Threshold | Observed | Status |",
        "| --- | :---: | :---: | :---: | :---: |",
    ]

    for tr in report.threshold_results:
        status = "PASSED" if tr.passed else "**FAILED**"
        lines.append(
            f"| `{tr.metric_name}` | `{tr.comparator}` | `{tr.threshold_value}` | `{tr.observed_value}` | {status} |"
        )

    lines.extend(
        [
            "",
            "### Data Slices Performance Summary",
            "",
            "| Dimension | Value | Samples | Min Sample Met? | OCR CER | Extraction F1 | Verification FNR | Verdict Accuracy |",
            "| --- | --- | :---: | :---: | :---: | :---: | :---: | :---: |",
        ]
    )

    for s in report.slice_summaries:
        met = "Yes" if s.sufficient_sample_size else "No"
        cer_str = f"{s.ocr_cer:.4f}" if s.ocr_cer is not None else "N/A"
        f1_str = f"{s.extraction_f1:.4f}" if s.extraction_f1 is not None else "N/A"
        fnr_str = (
            f"{s.verification_fnr:.4f}" if s.verification_fnr is not None else "N/A"
        )
        acc_str = (
            f"{s.verdict_accuracy:.4f}" if s.verdict_accuracy is not None else "N/A"
        )
        lines.append(
            f"| `{s.slice_dimension}` | `{s.slice_value}` | {s.sample_count} | {met} | `{cer_str}` | `{f1_str}` | `{fnr_str}` | `{acc_str}` |"
        )

    lines.extend(
        [
            "",
            "### Overall Component Metrics",
            "",
            f"- **OCR**: CER = `{report.overall_ocr.cer:.4f}`, WER = `{report.overall_ocr.wer:.4f}` ({report.overall_ocr.character_count} chars, {report.overall_ocr.word_count} words)",
            f"- **Extraction**: Precision = `{report.overall_extraction.precision:.4f}`, Recall = `{report.overall_extraction.recall:.4f}`, F1 = `{report.overall_extraction.f1:.4f}`, Line-Item F1 = `{report.overall_extraction.line_item_f1:.4f}`, Grounding Rate = `{report.overall_extraction.grounded_evidence_rate:.4f}`",
            f"- **Verification**: Rules Evaluated = {report.overall_verification.rules_evaluated}, TPR = `{report.overall_verification.tpr:.4f}`, TNR = `{report.overall_verification.tnr:.4f}`, FPR = `{report.overall_verification.fpr:.4f}`, FNR = `{report.overall_verification.fnr:.4f}`, Verdict Concordance = `{report.overall_verification.verdict_concordance:.4f}`",
            f"- **Explanation**: Guardrail Pass Rate = `{report.overall_explanation.guardrail_pass_rate:.4f}` ({report.overall_explanation.guardrail_passes} passes, {report.overall_explanation.guardrail_rejections} rejections), Fallback Invocations = {report.overall_explanation.fallback_invocations}, Numerical Contradictions = {report.overall_explanation.numerical_contradictions}",
            f"- **Performance**: Requests = {report.overall_performance.request_count}, p50 = `{report.overall_performance.p50_latency_seconds:.3f}s`, p95 = `{report.overall_performance.p95_latency_seconds:.3f}s`, p99 = `{report.overall_performance.p99_latency_seconds:.3f}s`, Throughput = `{report.overall_performance.requests_per_second:.2f} rps`",
            "",
            "### Limitations & Exceptions",
            "",
        ]
    )

    if report.limitations:
        for lim in report.limitations:
            lines.append(f"- {lim}")
    else:
        lines.append("- None declared.")

    if report.exceptions:
        lines.append("")
        lines.append("#### Approved Exceptions")
        for exc in report.exceptions:
            lines.append(f"- {exc}")

    if report.expiry_date:
        lines.append("")
        lines.append(
            f"> **Report Expiration Date**: `{report.expiry_date}` (Must re-evaluate before expiration)"
        )

    lines.append("")
    return "\n".join(lines)
