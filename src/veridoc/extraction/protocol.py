"""Provider-neutral boundary for structured invoice extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from veridoc.extraction.models import InvoiceExtraction
from veridoc.ocr.models import OCRDocumentResult, RenderedPage


@dataclass(frozen=True, slots=True)
class ExtractionRequest:
    """OCR text and page images supplied to one structured extractor."""

    document: OCRDocumentResult
    page_images: tuple[RenderedPage, ...]

    def __post_init__(self) -> None:
        """Ensure each OCR page has one ordered visual counterpart."""
        expected_page_numbers = tuple(range(1, len(self.document.pages) + 1))
        actual_page_numbers = tuple(page.page_number for page in self.page_images)
        if actual_page_numbers != expected_page_numbers:
            raise ValueError("Page images must align with the OCR page order.")


@runtime_checkable
class StructuredExtractor(Protocol):
    """Extract typed invoice fields from normalized OCR and image inputs."""

    async def extract(self, request: ExtractionRequest) -> InvoiceExtraction:
        """Return the structured extraction result for one validated document."""


class ExtractionUnavailableError(RuntimeError):
    """Raised when the configured extraction provider cannot be used safely."""

    code = "extraction_unavailable"
    message = "Structured extraction is not available on this server."

    def __init__(self) -> None:
        super().__init__(self.message)


class ExtractionProcessingError(RuntimeError):
    """Raised when structured extraction did not yield a valid result."""

    code = "extraction_processing_failed"
    message = "The document could not be extracted safely."

    def __init__(self) -> None:
        super().__init__(self.message)
