"""Command-line interface for the Veridoc evaluation and readiness benchmark."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from collections.abc import Sequence
from pathlib import Path

from veridoc.evaluation.decision import create_evaluation_report, render_markdown_report
from veridoc.evaluation.identity import (
    capture_artifact_identity,
    capture_provider_identity,
)
from veridoc.evaluation.manifest import CorpusManifestError
from veridoc.evaluation.models import EvaluationReport, EvaluationThresholds
from veridoc.evaluation.runner import EvaluationRunner
from veridoc.explanation.config import OpenAIExplanationSettings
from veridoc.explanation.openai_responses import OpenAIResponsesExplainer
from veridoc.explanation.protocol import ExplanationUnavailableError
from veridoc.explanation.service import ExplanationService
from veridoc.extraction.config import OpenAIExtractionSettings
from veridoc.extraction.openai_responses import OpenAIResponsesExtractor
from veridoc.ocr.protocol import OCREngine
from veridoc.ocr.tesseract import TesseractEngine
from veridoc.persistence.sqlite import SQLiteInvoiceRepository
from veridoc.processing.service import ProcessingService
from veridoc.verification.service import VerificationService


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for veridoc-evaluate."""
    parser = argparse.ArgumentParser(
        prog="veridoc-evaluate",
        description="Run Veridoc evaluation benchmark, compute metrics, and produce a production decision report.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Path to the corpus manifest JSON file.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Optional destination path to write the EvaluationReport JSON.",
    )
    parser.add_argument(
        "--output-markdown",
        type=Path,
        default=None,
        help="Optional destination path to write the Markdown report.",
    )
    parser.add_argument(
        "--reference-db",
        type=Path,
        default=None,
        help="Optional path to reference database. Defaults to VERIDOC_REFERENCE_DATABASE or temporary/in-memory.",
    )
    parser.add_argument(
        "--fail-on-no-go",
        action="store_true",
        help="Exit with non-zero status code (1) if the decision outcome is NO_GO.",
    )
    parser.add_argument(
        "--no-verify-integrity",
        action="store_true",
        help="Skip SHA-256 integrity verification of corpus files.",
    )
    parser.add_argument(
        "--evaluation-id",
        type=str,
        default=None,
        help="Custom identifier for this evaluation run.",
    )
    parser.add_argument(
        "--expiry-date",
        type=str,
        default=None,
        help="Optional expiration date for the evaluation report (YYYY-MM-DD).",
    )
    return parser.parse_args(argv)


async def _run_evaluation(
    args: argparse.Namespace,
    *,
    ocr_engine: OCREngine | None = None,
    processing_service: ProcessingService | None = None,
) -> EvaluationReport:
    manifest_path: Path = args.manifest.resolve()
    eval_id = args.evaluation_id or f"eval-{uuid.uuid4().hex[:12]}"

    engine = ocr_engine or TesseractEngine()

    if processing_service is None:
        db_path = str(
            args.reference_db
            or os.environ.get("VERIDOC_REFERENCE_DATABASE", "veridoc-reference.sqlite3")
        )
        repo = SQLiteInvoiceRepository(db_path)
        repo.initialize()

        verification_service = VerificationService(repo)

        try:
            exp_settings = OpenAIExplanationSettings.from_environment()
            explainer = OpenAIResponsesExplainer(exp_settings)
            explanation_service = ExplanationService(explainer)
        except (ExplanationUnavailableError, RuntimeError, ValueError):
            explanation_service = ExplanationService()

        try:
            ext_settings = OpenAIExtractionSettings.from_environment()
            extractor = OpenAIResponsesExtractor(ext_settings)
        except (RuntimeError, ValueError):
            raise RuntimeError(
                "VERIDOC_LLM_API_KEY must be configured to run structured extraction in evaluation."
            ) from None

        service = ProcessingService(
            engine,
            extractor,
            verification_service,
            explanation_service,
        )
    else:
        service = processing_service

    runner = EvaluationRunner(engine, service)
    thresholds = EvaluationThresholds()

    (
        manifest,
        overall_ocr,
        overall_extraction,
        overall_verification,
        overall_explanation,
        overall_performance,
        slice_summaries,
    ) = await runner.run(
        manifest_path,
        verify_integrity=not args.no_verify_integrity,
        thresholds=thresholds,
    )

    artifact_identity = capture_artifact_identity()
    provider_identity = capture_provider_identity()

    report = create_evaluation_report(
        evaluation_id=eval_id,
        manifest_name=manifest.corpus_name,
        manifest_version=manifest.manifest_version,
        total_documents=len(manifest.documents),
        artifact_identity=artifact_identity,
        provider_identity=provider_identity,
        thresholds=thresholds,
        overall_ocr=overall_ocr,
        overall_extraction=overall_extraction,
        overall_verification=overall_verification,
        overall_explanation=overall_explanation,
        overall_performance=overall_performance,
        slice_summaries=slice_summaries,
        expiry_date=args.expiry_date,
    )

    return report


def main(
    argv: Sequence[str] | None = None,
    *,
    ocr_engine: OCREngine | None = None,
    processing_service: ProcessingService | None = None,
) -> int:
    """CLI entry point for veridoc-evaluate."""
    args = parse_args(argv)

    try:
        report = asyncio.run(
            _run_evaluation(
                args,
                ocr_engine=ocr_engine,
                processing_service=processing_service,
            )
        )
    except (CorpusManifestError, RuntimeError, OSError, ValueError) as exc:
        sys.stderr.write(f"Evaluation error: {exc}\n")
        return 2

    markdown = render_markdown_report(report)

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    if args.output_markdown:
        args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.output_markdown.write_text(markdown, encoding="utf-8")

    sys.stdout.write(markdown)

    if args.fail_on_no_go and report.decision == "no_go":
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
