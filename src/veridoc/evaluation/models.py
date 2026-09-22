"""Domain models and schemas for Phase 11 evaluation and readiness decisions."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

LanguageSlice = Literal["eng", "ara", "mixed"]
QualitySlice = Literal["clean", "noisy"]
LayoutSlice = Literal["standard", "dense", "sparse"]
LicenseType = Literal["synthetic", "public-licensed", "proprietary-governed"]
DecisionOutcome = Literal["go", "conditional_go", "no_go"]


class StrictEvaluationModel(BaseModel):
    """Base model enforcing strict schemas without extra attributes."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class GroundTruthLineItem(StrictEvaluationModel):
    """Ground truth for a single line item in an invoice."""

    description: str
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    total_amount: Decimal | None = None


class GroundTruthInvoice(StrictEvaluationModel):
    """Ground truth annotations for an evaluation invoice."""

    invoice_number: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    vendor_name: str | None = None
    vendor_tax_id: str | None = None
    currency: str | None = None
    total_amount: Decimal | None = None
    subtotal_amount: Decimal | None = None
    tax_amount: Decimal | None = None
    line_items: list[GroundTruthLineItem] = Field(default_factory=list)
    expected_finding_types: list[str] = Field(default_factory=list)
    expected_verdict: Literal["clear", "review_required"] = "clear"
    ocr_transcript: str | None = None


class CorpusDocument(StrictEvaluationModel):
    """A document entry in the evaluation corpus manifest."""

    document_id: str = Field(..., min_length=1, max_length=128)
    file_path: str = Field(..., min_length=1, max_length=512)
    file_sha256: str = Field(
        ..., min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    mime_type: Literal["application/pdf", "image/png", "image/jpeg"]
    page_count: int = Field(..., ge=1, le=20)
    license: LicenseType
    provenance: str = Field(..., min_length=1, max_length=256)
    language: LanguageSlice
    quality: QualitySlice
    layout: LayoutSlice
    ground_truth_path: str = Field(..., min_length=1, max_length=512)
    ground_truth_sha256: str = Field(
        ..., min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )


class CorpusManifest(StrictEvaluationModel):
    """Schema for a versioned evaluation corpus manifest."""

    manifest_version: Literal["1.0"] = "1.0"
    corpus_name: str = Field(..., min_length=1, max_length=128)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    description: str = Field(..., min_length=1, max_length=1024)
    documents: list[CorpusDocument] = Field(..., min_length=1)


class EvaluationThresholds(StrictEvaluationModel):
    """Preregistered acceptance thresholds for Phase 11 evaluation."""

    max_ocr_cer: Annotated[float, Field(ge=0.0, le=1.0)] = 0.05
    max_ocr_wer: Annotated[float, Field(ge=0.0, le=1.0)] = 0.15
    min_extraction_f1: Annotated[float, Field(ge=0.0, le=1.0)] = 0.90
    min_line_item_f1: Annotated[float, Field(ge=0.0, le=1.0)] = 0.85
    max_verification_fnr: Annotated[float, Field(ge=0.0, le=1.0)] = 0.00
    min_verdict_accuracy: Annotated[float, Field(ge=0.0, le=1.0)] = 0.95
    min_guardrail_pass_rate: Annotated[float, Field(ge=0.0, le=1.0)] = 0.99
    max_p95_latency_seconds: Annotated[float, Field(ge=0.1, le=120.0)] = 10.0
    min_slice_sample_count: Annotated[int, Field(ge=1, le=1000)] = 10


class OCRMetrics(StrictEvaluationModel):
    """OCR evaluation metrics for character and word error rates."""

    character_count: int = Field(ge=0)
    word_count: int = Field(ge=0)
    character_errors: int = Field(ge=0)
    word_errors: int = Field(ge=0)
    cer: float = Field(ge=0.0)
    wer: float = Field(ge=0.0)


class ExtractionMetrics(StrictEvaluationModel):
    """Field-level and line-item extraction metrics."""

    field_count: int = Field(ge=0)
    exact_match_count: int = Field(ge=0)
    precision: float = Field(ge=0.0, le=1.0)
    recall: float = Field(ge=0.0, le=1.0)
    f1: float = Field(ge=0.0, le=1.0)
    line_item_f1: float = Field(ge=0.0, le=1.0)
    grounded_evidence_rate: float = Field(ge=0.0, le=1.0)


class VerificationMetrics(StrictEvaluationModel):
    """Deterministic verification rule and verdict metrics."""

    rules_evaluated: int = Field(ge=0)
    true_positives: int = Field(ge=0)
    true_negatives: int = Field(ge=0)
    false_positives: int = Field(ge=0)
    false_negatives: int = Field(ge=0)
    tpr: float = Field(ge=0.0, le=1.0)
    tnr: float = Field(ge=0.0, le=1.0)
    fpr: float = Field(ge=0.0, le=1.0)
    fnr: float = Field(ge=0.0, le=1.0)
    verdict_concordance: float = Field(ge=0.0, le=1.0)


class ExplanationMetrics(StrictEvaluationModel):
    """Explanation guardrail and fallback safety metrics."""

    total_explanations: int = Field(ge=0)
    guardrail_passes: int = Field(ge=0)
    guardrail_rejections: int = Field(ge=0)
    guardrail_pass_rate: float = Field(ge=0.0, le=1.0)
    numerical_contradictions: int = Field(ge=0)
    fallback_invocations: int = Field(ge=0)


class PerformanceMetrics(StrictEvaluationModel):
    """End-to-end performance and latency metrics."""

    request_count: int = Field(ge=0)
    p50_latency_seconds: float = Field(ge=0.0)
    p95_latency_seconds: float = Field(ge=0.0)
    p99_latency_seconds: float = Field(ge=0.0)
    requests_per_second: float = Field(ge=0.0)
    timeout_failures: int = Field(ge=0)
    concurrency_rejections: int = Field(ge=0)


class ConfidenceInterval(StrictEvaluationModel):
    """Wilson score confidence interval for a metric."""

    point_estimate: float
    lower_bound: float
    upper_bound: float
    confidence_level: float = 0.95


class SliceMetricsSummary(StrictEvaluationModel):
    """Aggregated metrics and sample count for a specific slice."""

    slice_dimension: Literal["language", "quality", "layout", "page_count", "overall"]
    slice_value: str
    sample_count: int = Field(ge=0)
    sufficient_sample_size: bool
    ocr_cer: float | None = None
    ocr_wer: float | None = None
    extraction_f1: float | None = None
    line_item_f1: float | None = None
    verification_fnr: float | None = None
    verdict_accuracy: float | None = None
    cer_ci: ConfidenceInterval | None = None
    f1_ci: ConfidenceInterval | None = None


class ThresholdEvaluationResult(StrictEvaluationModel):
    """Comparison of an observed metric against its threshold."""

    metric_name: str
    observed_value: float
    threshold_value: float
    comparator: Literal["<=", ">="]
    passed: bool
    slice_dimension: str = "overall"
    slice_value: str = "all"


class ArtifactIdentityRecord(StrictEvaluationModel):
    """Fingerprint of the application artifact under evaluation."""

    app_version: str
    git_commit: str
    python_version: str
    platform: str
    lockfile_sha256: str
    tesseract_version: str | None = None
    tessdata_sha256: dict[str, str] = Field(default_factory=dict)
    reference_schema_version: int
    review_schema_version: int


class ProviderIdentityRecord(StrictEvaluationModel):
    """Fingerprint of the structured extraction/explanation provider."""

    model_name: str
    system_prompt_sha256: str
    extraction_schema_sha256: str
    temperature: float = 0.0
    timeout_seconds: float = 120.0
    provider_system_fingerprint: str | None = None


class EvaluationReport(StrictEvaluationModel):
    """Comprehensive evaluation report and production readiness decision."""

    evaluation_id: str = Field(..., min_length=1, max_length=128)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    manifest_name: str
    manifest_version: str
    total_documents: int = Field(ge=1)
    artifact_identity: ArtifactIdentityRecord
    provider_identity: ProviderIdentityRecord
    thresholds: EvaluationThresholds
    threshold_results: list[ThresholdEvaluationResult]
    slice_summaries: list[SliceMetricsSummary]
    overall_ocr: OCRMetrics
    overall_extraction: ExtractionMetrics
    overall_verification: VerificationMetrics
    overall_explanation: ExplanationMetrics
    overall_performance: PerformanceMetrics
    decision: DecisionOutcome
    decision_rationale: str
    limitations: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    expiry_date: str | None = None
