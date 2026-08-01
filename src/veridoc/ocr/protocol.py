"""Replaceable OCR engine boundary."""

from typing import Protocol

from PIL import Image

from veridoc.ocr.models import OCRPageResult


class OCREngine(Protocol):
    """Recognize text from one already validated and decoded page image."""

    def recognize(self, image: Image.Image) -> OCRPageResult:
        """Return raw text and optional engine confidence for a page."""


class OCRUnavailableError(RuntimeError):
    """Raised when the configured OCR executable or language data is unavailable."""

    code = "ocr_unavailable"
    message = "OCR is not available on this server."


class OCRProcessingError(RuntimeError):
    """Raised when a validated document cannot be processed safely."""

    code = "ocr_processing_failed"
    message = "The document could not be processed safely."
