"""Document decoding and OCR orchestration for the Phase 1 boundary."""

from __future__ import annotations

from collections.abc import Buffer, Iterator
from io import BytesIO
from math import isfinite
from pathlib import Path

import pymupdf
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
                            encoded_image = _encode_png(
                                image,
                                max_bytes=(
                                    MAX_PAGE_IMAGE_BUNDLE_BYTES - page_image_bytes
                                ),
                            )
                            page_image_bytes += len(encoded_image)
                            if page_image_bytes > MAX_PAGE_IMAGE_BUNDLE_BYTES:
                                raise OCRProcessingError
                        pages.append(
                            _normalized_page_result(self._engine.recognize(image))
                        )
                        if encoded_image is not None:
                            page_images.append(
                                RenderedPage(
                                    page_number=page_number,
                                    image_bytes=encoded_image,
                                )
                            )
                    finally:
                        image.close()
        except (OCRUnavailableError, OCRProcessingError):
            raise
        except (OSError, RuntimeError, pymupdf.FileDataError) as exc:
            raise OCRProcessingError from exc

        if not pages:
            raise OCRProcessingError
        return OCRDocumentBundle(
            document=OCRDocumentResult(
                media_type=upload.media_type, pages=tuple(pages)
            ),
            page_images=tuple(page_images),
        )


def _normalized_page_result(result: object) -> OCRPageResult:
    """Reject malformed engine output and discard invalid confidence values."""
    if not isinstance(result, OCRPageResult) or not isinstance(result.text, str):
        raise OCRProcessingError
    confidence = result.confidence
    if (
        not isinstance(confidence, float)
        or not isfinite(confidence)
        or not 0 <= confidence <= 100
    ):
        return OCRPageResult(text=result.text, confidence=None)
    return result


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
        document = pymupdf.open(path)
    except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
        raise OCRProcessingError from exc

    try:
        for page in document:
            pixmap = page.get_pixmap(dpi=PDF_RENDER_DPI, alpha=False)
            yield Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    except (RuntimeError, ValueError, OSError) as exc:
        raise OCRProcessingError from exc
    finally:
        document.close()


class _BoundedBytesIO(BytesIO):
    def __init__(self, max_bytes: int) -> None:
        super().__init__()
        self._max_bytes = max_bytes

    def write(self, data: Buffer, /) -> int:
        if self.tell() + memoryview(data).nbytes > self._max_bytes:
            raise OCRProcessingError
        return super().write(data)


def _encode_png(image: Image.Image, *, max_bytes: int) -> bytes:
    """Encode one normalized page as PNG without retaining a temporary file."""
    output = _BoundedBytesIO(max_bytes)
    image.save(output, format="PNG")
    return output.getvalue()
