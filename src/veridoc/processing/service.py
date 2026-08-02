"""API-neutral service for complete invoice processing."""

from __future__ import annotations

from veridoc.explanation.service import ExplanationService
from veridoc.extraction.protocol import StructuredExtractor
from veridoc.ingestion.models import ValidatedUpload
from veridoc.ocr.protocol import OCREngine
from veridoc.processing.graph import build_processing_graph
from veridoc.processing.models import ProcessingResult
from veridoc.verification.service import VerificationService


class ProcessingError(RuntimeError):
    """Raised when the complete graph does not produce a typed result."""

    code = "processing_failed"
    message = "The document could not be processed safely."

    def __init__(self) -> None:
        super().__init__(self.message)


class ProcessingService:
    """Run a validated invoice through every implemented processing stage."""

    def __init__(
        self,
        ocr_engine: OCREngine,
        extractor: StructuredExtractor,
        verification_service: VerificationService,
        explanation_service: ExplanationService,
    ) -> None:
        self._graph = build_processing_graph(
            ocr_engine,
            extractor,
            verification_service,
            explanation_service,
        )

    async def process(self, upload: ValidatedUpload) -> ProcessingResult:
        """Return the complete typed result for one validated document."""
        state = await self._graph.ainvoke({"upload": upload})
        result = state.get("result")
        if not isinstance(result, ProcessingResult):
            raise ProcessingError
        return result
