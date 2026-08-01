"""Safe conversion of validated invoices into OCR-ready page images."""

from io import BytesIO
from typing import Final

import fitz
from PIL import Image, UnidentifiedImageError

from veridoc.ingestion.models import RasterPage, UploadedDocument

MAX_DOCUMENT_PAGES: Final = 20
MAX_IMAGE_PIXELS: Final = 40_000_000


class DocumentDecodingError(ValueError):
    """Raised when a validated invoice cannot be decoded safely."""


def decode_document(document: UploadedDocument) -> tuple[RasterPage, ...]:
    """Render a validated image or PDF invoice into one or more PNG pages."""
    if document.media_type == "application/pdf":
        return _render_pdf(document.content)
    return (_normalize_image(document.content),)


def _render_pdf(content: bytes) -> tuple[RasterPage, ...]:
    """Render each PDF page at OCR-friendly resolution within page limits."""
    try:
        pdf = fitz.open(stream=content, filetype="pdf")
    except (fitz.FileDataError, RuntimeError, ValueError) as error:
        raise DocumentDecodingError("The uploaded PDF could not be decoded.") from error

    try:
        if pdf.page_count == 0:
            raise DocumentDecodingError("The uploaded PDF contains no pages.")
        if pdf.page_count > MAX_DOCUMENT_PAGES:
            raise DocumentDecodingError(
                f"Invoice PDFs must not exceed {MAX_DOCUMENT_PAGES} pages."
            )
        return tuple(
            RasterPage(
                page_number=page_index + 1,
                image_bytes=pdf.load_page(page_index)
                .get_pixmap(dpi=200, alpha=False)
                .tobytes("png"),
            )
            for page_index in range(pdf.page_count)
        )
    except (fitz.FileDataError, RuntimeError, ValueError) as error:
        raise DocumentDecodingError("The uploaded PDF could not be rendered.") from error
    finally:
        pdf.close()


def _normalize_image(content: bytes) -> RasterPage:
    """Decode an image and normalize it to a PNG page for OCR."""
    try:
        with Image.open(BytesIO(content)) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise DocumentDecodingError(
                    f"Invoice images must not exceed {MAX_IMAGE_PIXELS} pixels."
                )
            normalized = image.convert("RGB")
            output = BytesIO()
            normalized.save(output, format="PNG")
    except (OSError, UnidentifiedImageError) as error:
        raise DocumentDecodingError("The uploaded image could not be decoded.") from error

    return RasterPage(page_number=1, image_bytes=output.getvalue())
