"""Shared FastAPI dependencies composing the complete processing pipeline.

Kept separate from ``veridoc.app`` so both ``veridoc.app`` and
``veridoc.review.api`` can depend on the identical OCR-to-verdict pipeline
without importing from each other.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends

from veridoc.explanation.config import OpenAIExplanationSettings
from veridoc.explanation.openai_responses import OpenAIResponsesExplainer
from veridoc.explanation.protocol import ExplanationUnavailableError
from veridoc.explanation.service import ExplanationService
from veridoc.extraction.config import OpenAIExtractionSettings
from veridoc.extraction.openai_responses import OpenAIResponsesExtractor
from veridoc.extraction.protocol import StructuredExtractor
from veridoc.ocr.protocol import OCREngine
from veridoc.ocr.tesseract import TesseractEngine
from veridoc.persistence.protocol import InvoiceRepository
from veridoc.persistence.sqlite import SQLiteInvoiceRepository
from veridoc.processing.service import ProcessingService
from veridoc.verification.service import VerificationService


def get_ocr_engine() -> OCREngine:
    """Build the configured OCR engine for one request."""
    return TesseractEngine()


async def get_structured_extractor() -> AsyncIterator[StructuredExtractor]:
    """Yield one configured extraction adapter and close its provider client."""
    settings = OpenAIExtractionSettings.from_environment()
    extractor = OpenAIResponsesExtractor(settings)
    try:
        yield extractor
    finally:
        await extractor.aclose()


def get_invoice_repository() -> InvoiceRepository:
    """Open and initialize the configured local reference-data repository."""
    database_path = os.environ.get(
        "VERIDOC_REFERENCE_DATABASE", "veridoc-reference.sqlite3"
    ).strip()
    repository = SQLiteInvoiceRepository(database_path or "veridoc-reference.sqlite3")
    repository.initialize()
    return repository


def get_verification_service(
    repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
) -> VerificationService:
    """Build the deterministic verification service for one processing request."""
    return VerificationService(repository)


async def get_explanation_service() -> AsyncIterator[ExplanationService]:
    """Yield optional provider guidance and close any configured client."""
    try:
        settings = OpenAIExplanationSettings.from_environment()
    except ExplanationUnavailableError:
        yield ExplanationService()
        return

    explainer = OpenAIResponsesExplainer(settings)
    try:
        yield ExplanationService(explainer)
    finally:
        await explainer.aclose()


def get_processing_service(
    ocr_engine: Annotated[OCREngine, Depends(get_ocr_engine)],
    extractor: Annotated[StructuredExtractor, Depends(get_structured_extractor)],
    verification_service: Annotated[
        VerificationService, Depends(get_verification_service)
    ],
    explanation_service: Annotated[
        ExplanationService, Depends(get_explanation_service)
    ],
) -> ProcessingService:
    """Compose the complete typed processing graph for one API request."""
    return ProcessingService(
        ocr_engine,
        extractor,
        verification_service,
        explanation_service,
    )
