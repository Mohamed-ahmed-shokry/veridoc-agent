"""Deterministic evaluation runner and uncertainty quantification."""

from __future__ import annotations

import math
import time
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Final, Literal

from veridoc.evaluation.manifest import load_corpus_manifest
from veridoc.evaluation.metrics.explanation import aggregate_explanation_metrics
from veridoc.evaluation.metrics.extraction import aggregate_extraction_metrics
from veridoc.evaluation.metrics.ocr import aggregate_ocr_metrics
from veridoc.evaluation.metrics.verification import aggregate_verification_metrics
from veridoc.evaluation.models import (
    ConfidenceInterval,
    CorpusManifest,
    EvaluationThresholds,
    ExplanationMetrics,
    ExtractionMetrics,
    GroundTruthInvoice,
    OCRMetrics,
    PerformanceMetrics,
    SliceMetricsSummary,
    VerificationMetrics,
)
from veridoc.explanation.models import FindingExplanation
from veridoc.extraction.models import InvoiceExtraction
from veridoc.ingestion.models import ValidatedUpload
from veridoc.ocr.protocol import OCREngine
from veridoc.ocr.service import OCRService
from veridoc.processing.models import ProcessingResult
from veridoc.processing.service import ProcessingService
from veridoc.verification.models import VerificationFinding

# Z-value for 95% two-sided normal confidence interval
Z_95: Final[float] = 1.959963984540054


def wilson_score_interval(
    successes: int,
    total: int,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Compute the Wilson score confidence interval for a binomial proportion."""
    if total <= 0:
        return 0.0, 1.0

    z = Z_95 if math.isclose(confidence, 0.95, abs_tol=1e-3) else 1.96
    p_hat = successes / total
    z2 = z * z
    n = float(total)

    denominator = 1.0 + (z2 / n)
    center = (p_hat + (z2 / (2.0 * n))) / denominator
    margin = (z / denominator) * math.sqrt(
        (p_hat * (1.0 - p_hat) / n) + (z2 / (4.0 * n * n))
    )

    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return round(lower, 4), round(upper, 4)


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_v[int(k)]
    return sorted_v[f] * (c - k) + sorted_v[c] * (k - f)


class EvaluationRunner:
    """Execute evaluation over a corpus manifest and compute aggregate and slice metrics."""

    def __init__(
        self,
        ocr_engine: OCREngine,
        processing_service: ProcessingService,
    ) -> None:
        self._ocr_service = OCRService(ocr_engine)
        self._processing_service = processing_service

    async def run(
        self,
        manifest_path: Path,
        *,
        verify_integrity: bool = True,
        thresholds: EvaluationThresholds | None = None,
    ) -> tuple[
        CorpusManifest,
        OCRMetrics,
        ExtractionMetrics,
        VerificationMetrics,
        ExplanationMetrics,
        PerformanceMetrics,
        list[SliceMetricsSummary],
    ]:
        """Run evaluation over all documents in the manifest."""
        manifest, gt_map = load_corpus_manifest(
            manifest_path, verify_integrity=verify_integrity
        )
        corpus_root = manifest_path.parent

        ocr_pairs: list[tuple[str, str]] = []
        extraction_pairs: list[tuple[InvoiceExtraction, GroundTruthInvoice]] = []
        verification_cases: list[
            tuple[Sequence[VerificationFinding], str, GroundTruthInvoice]
        ] = []
        all_explanations: list[FindingExplanation] = []
        latencies: list[float] = []

        # Slice buckets: (dimension, value) -> list of document indices
        slice_indices: dict[
            tuple[Literal["language", "quality", "layout", "page_count"], str],
            list[int],
        ] = defaultdict(list)

        per_doc_ocr: list[tuple[str, str]] = []
        per_doc_extraction: list[tuple[InvoiceExtraction, GroundTruthInvoice]] = []
        per_doc_verification: list[
            tuple[Sequence[VerificationFinding], str, GroundTruthInvoice]
        ] = []

        for idx, doc in enumerate(manifest.documents):
            gt = gt_map[doc.document_id]
            doc_file = corpus_root / doc.file_path
            data = doc_file.read_bytes()

            upload = ValidatedUpload(
                data=data,
                media_type=doc.mime_type,
                filename=doc_file.name,
                suffix=doc_file.suffix,
                page_count=doc.page_count,
            )

            t0 = time.perf_counter()
            ocr_result = self._ocr_service.process(upload)
            proc_result: ProcessingResult = await self._processing_service.process(
                upload
            )
            t1 = time.perf_counter()

            latencies.append(t1 - t0)

            hyp_ocr = "\n".join(p.text for p in ocr_result.pages)
            ocr_pair = (gt.ocr_transcript or "", hyp_ocr)
            ext_pair = (proc_result.extraction, gt)
            ver_case = (proc_result.findings, proc_result.verdict.status, gt)

            ocr_pairs.append(ocr_pair)
            extraction_pairs.append(ext_pair)
            verification_cases.append(ver_case)
            all_explanations.extend(proc_result.explanations)

            per_doc_ocr.append(ocr_pair)
            per_doc_extraction.append(ext_pair)
            per_doc_verification.append(ver_case)

            # Record slice tags
            slice_indices[("language", str(doc.language))].append(idx)
            slice_indices[("quality", str(doc.quality))].append(idx)
            slice_indices[("layout", str(doc.layout))].append(idx)
            slice_indices[
                ("page_count", "multi" if doc.page_count >= 2 else "single")
            ].append(idx)

        # Aggregate overall metrics
        overall_ocr = aggregate_ocr_metrics(ocr_pairs)
        overall_extraction = aggregate_extraction_metrics(extraction_pairs)
        overall_verification = aggregate_verification_metrics(verification_cases)
        overall_explanation = aggregate_explanation_metrics(all_explanations)

        # Compute performance metrics
        total_requests = len(latencies)
        total_time = sum(latencies)
        p50 = round(_percentile(latencies, 0.50), 4)
        p95 = round(_percentile(latencies, 0.95), 4)
        p99 = round(_percentile(latencies, 0.99), 4)
        rps = round(total_requests / total_time, 2) if total_time > 0 else 0.0

        overall_performance = PerformanceMetrics(
            request_count=total_requests,
            p50_latency_seconds=p50,
            p95_latency_seconds=p95,
            p99_latency_seconds=p99,
            requests_per_second=rps,
            timeout_failures=0,
            concurrency_rejections=0,
        )

        min_sample = thresholds.min_slice_sample_count if thresholds is not None else 10

        # Compute slice summaries
        slice_summaries: list[SliceMetricsSummary] = []
        for (dim, val), doc_indices in sorted(slice_indices.items()):
            sub_ocr = aggregate_ocr_metrics([per_doc_ocr[i] for i in doc_indices])
            sub_ext = aggregate_extraction_metrics(
                [per_doc_extraction[i] for i in doc_indices]
            )
            sub_ver = aggregate_verification_metrics(
                [per_doc_verification[i] for i in doc_indices]
            )

            f1_lower, f1_upper = wilson_score_interval(
                sub_ext.exact_match_count, sub_ext.field_count
            )

            slice_summaries.append(
                SliceMetricsSummary(
                    slice_dimension=dim,
                    slice_value=val,
                    sample_count=len(doc_indices),
                    sufficient_sample_size=len(doc_indices) >= min_sample,
                    ocr_cer=sub_ocr.cer,
                    ocr_wer=sub_ocr.wer,
                    extraction_f1=sub_ext.f1,
                    line_item_f1=sub_ext.line_item_f1,
                    verification_fnr=sub_ver.fnr,
                    verdict_accuracy=sub_ver.verdict_concordance,
                    f1_ci=ConfidenceInterval(
                        point_estimate=sub_ext.f1,
                        lower_bound=f1_lower,
                        upper_bound=f1_upper,
                    ),
                )
            )

        return (
            manifest,
            overall_ocr,
            overall_extraction,
            overall_verification,
            overall_explanation,
            overall_performance,
            slice_summaries,
        )
