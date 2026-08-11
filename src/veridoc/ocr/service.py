"""Document decoding and OCR orchestration for the Phase 1 boundary."""

from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import fitz
from PIL import Image, UnidentifiedImageError

from veridoc.ingestion.models import DocumentMediaType, ValidatedUpload
from veridoc.ingestion.storage import temporary_upload
from veridoc.ingestion.validation import PDF_RENDER_DPI
from veridoc.ocr.models import (
    OCRDocumentBundle,
    OCRDocumentResult,
    OCRPageResult,
    RenderedPage,
)
from veridoc.ocr.protocol import OCREngine, OCRProcessingError, OCRUnavailableError

MAX_PAGE_IMAGE_BUNDLE_BYTES = 32 * 1024 * 1024


class OCRService:
    """Decode validated uploads and send each page to an injected OCR engine."""

    def __init__(self, engine: OCREngine) -> None:
        self._engine = engine

    def process(self, upload: ValidatedUpload) -> OCRDocumentResult:
        """Return typed OCR output while cleaning all temporary processing files."""
        return self._process(upload, include_page_images=False).document

    def process_with_page_images(self, upload: ValidatedUpload) -> OCRDocumentBundle:
        """Return OCR output and normalized page images for vision extraction."""
        return self._process(upload, include_page_images=True)

    def _process(
        self, upload: ValidatedUpload, *, include_page_images: bool
    ) -> OCRDocumentBundle:
        pages: list[OCRPageResult] = []
        page_images: list[RenderedPage] = []
        page_image_bytes = 0
        try:
            with temporary_upload(upload) as path:
                for page_number, image in enumerate(
                    _iter_page_images(path, upload.media_type), start=1
                ):
                    try:
                        encoded_image: bytes | None = None
                        if include_page_images:
                            encoded_image = _encode_png(image)
                            page_image_bytes += len(encoded_image)
                            if page_image_bytes > MAX_PAGE_IMAGE_BUNDLE_BYTES:
                                raise OCRProcessingError
                        pages.append(self._engine.recognize(image))
                        if encoded_image is not None:
                            page_images.append(
                                RenderedPage(
                                    page_number=page_number,
                                    image_bytes=encoded_image,
                                )
                            )
                    finally:
                        image.close()
        except OCRUnavailableError:
            raise
        except (OSError, RuntimeError, fitz.FileDataError) as exc:
            raise OCRProcessingError from exc

        if not pages:
            raise OCRProcessingError
        return OCRDocumentBundle(
            document=OCRDocumentResult(
                media_type=upload.media_type, pages=tuple(pages)
            ),
            page_images=tuple(page_images),
        )


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
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as exc:
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


def _encode_png(image: Image.Image) -> bytes:
    """Encode one normalized page as PNG without retaining a temporary file."""
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
