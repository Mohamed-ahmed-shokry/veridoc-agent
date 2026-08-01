"""Document decoding and OCR orchestration for the Phase 1 boundary."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import fitz
from PIL import Image

from veridoc.ingestion.models import DocumentMediaType, ValidatedUpload
from veridoc.ingestion.storage import temporary_upload
from veridoc.ingestion.validation import PDF_RENDER_DPI
from veridoc.ocr.models import OCRDocumentResult, OCRPageResult
from veridoc.ocr.protocol import OCREngine, OCRProcessingError, OCRUnavailableError


class OCRService:
    """Decode validated uploads and send each page to an injected OCR engine."""

    def __init__(self, engine: OCREngine) -> None:
        self._engine = engine

    def process(self, upload: ValidatedUpload) -> OCRDocumentResult:
        """Return typed OCR output while cleaning all temporary processing files."""
        pages: list[OCRPageResult] = []
        try:
            with temporary_upload(upload) as path:
                for image in _iter_page_images(path, upload.media_type):
                    try:
                        pages.append(self._engine.recognize(image))
                    finally:
                        image.close()
        except OCRUnavailableError:
            raise
        except (OSError, RuntimeError, fitz.FileDataError) as exc:
            raise OCRProcessingError from exc

        if not pages:
            raise OCRProcessingError
        return OCRDocumentResult(media_type=upload.media_type, pages=tuple(pages))


def _iter_page_images(
    path: Path, media_type: DocumentMediaType
) -> Iterator[Image.Image]:
    if media_type == "application/pdf":
        yield from _iter_pdf_pages(path)
    else:
        yield from _iter_raster_page(path)


def _iter_raster_page(path: Path) -> Iterator[Image.Image]:
    try:
        with Image.open(path) as source:
            source.load()
            yield source.convert("RGB")
    except (Image.DecompressionBombError, Image.UnidentifiedImageError, OSError) as exc:
        raise OCRProcessingError from exc


def _iter_pdf_pages(path: Path) -> Iterator[Image.Image]:
    try:
        document = fitz.open(path)
    except (fitz.FileDataError, RuntimeError, ValueError) as exc:
        raise OCRProcessingError from exc

    try:
        for page in document:
            pixmap = page.get_pixmap(dpi=PDF_RENDER_DPI, alpha=False)
            yield Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    except (RuntimeError, ValueError, OSError) as exc:
        raise OCRProcessingError from exc
    finally:
        document.close()
