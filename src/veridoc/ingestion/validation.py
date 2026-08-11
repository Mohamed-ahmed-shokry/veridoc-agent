"""Bounded and signature-based validation for invoice uploads."""

from __future__ import annotations

import math
import re
import unicodedata
from io import BytesIO

import pymupdf
from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from veridoc.ingestion.models import DocumentMediaType, ValidatedUpload

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 20
MAX_IMAGE_PIXELS = 20_000_000
MAX_DOCUMENT_PIXELS = 50_000_000
PDF_RENDER_DPI = 150
READ_CHUNK_SIZE = 64 * 1024
MAX_FILENAME_LENGTH = 128

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"
_CONTENT_TYPE_ALIASES = {"image/jpg": "image/jpeg"}
_SUPPORTED_CONTENT_TYPES = frozenset({"application/pdf", "image/png", "image/jpeg"})


class UploadValidationError(ValueError):
    """Safe, client-facing validation failure for an uploaded document."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def sanitize_filename(filename: str | None) -> str:
    """Return a short display name without path, control, or shell characters."""
    candidate = (filename or "upload").replace("\\", "/").rsplit("/", 1)[-1]
    candidate = unicodedata.normalize("NFKC", candidate)
    candidate = "".join(character for character in candidate if character >= " ")
    candidate = re.sub(r"[^A-Za-z0-9._-]+", "_", candidate).strip("._")
    return candidate[:MAX_FILENAME_LENGTH] or "upload"


async def read_bounded_upload(upload: UploadFile) -> bytes:
    """Read an upload in chunks and reject it before exceeding the byte limit."""
    data = bytearray()
    while chunk := await upload.read(READ_CHUNK_SIZE):
        if len(data) + len(chunk) > MAX_UPLOAD_BYTES:
            raise UploadValidationError(
                "upload_too_large",
                f"Uploads must not exceed {MAX_UPLOAD_BYTES} bytes.",
                status_code=413,
            )
        data.extend(chunk)

    if not data:
        raise UploadValidationError("empty_upload", "The uploaded document is empty.")
    return bytes(data)


def validate_upload(
    data: bytes,
    *,
    filename: str | None,
    declared_content_type: str | None,
) -> ValidatedUpload:
    """Validate bytes, signature, metadata, and decode limits before processing."""
    if not data:
        raise UploadValidationError("empty_upload", "The uploaded document is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadValidationError(
            "upload_too_large",
            f"Uploads must not exceed {MAX_UPLOAD_BYTES} bytes.",
            status_code=413,
        )

    media_type = _detect_media_type(data)
    declared = _normalize_content_type(declared_content_type)
    if declared and declared not in _SUPPORTED_CONTENT_TYPES:
        raise UploadValidationError(
            "unsupported_content_type",
            "Only PDF, PNG, and JPEG documents are supported.",
            status_code=415,
        )
    if declared and declared != media_type:
        raise UploadValidationError(
            "content_type_mismatch",
            "The declared content type does not match the document signature.",
            status_code=415,
        )

    if media_type == "application/pdf":
        page_count = _validate_pdf(data)
        width = height = None
        suffix = ".pdf"
    else:
        page_count, width, height = _validate_image(data, media_type)
        suffix = ".png" if media_type == "image/png" else ".jpg"

    return ValidatedUpload(
        data=data,
        media_type=media_type,
        filename=sanitize_filename(filename),
        suffix=suffix,
        page_count=page_count,
        width=width,
        height=height,
    )


def _normalize_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    normalized = content_type.split(";", 1)[0].strip().lower()
    return _CONTENT_TYPE_ALIASES.get(normalized, normalized)


def _detect_media_type(data: bytes) -> DocumentMediaType:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(_PNG_SIGNATURE):
        return "image/png"
    if data.startswith(_JPEG_SIGNATURE):
        return "image/jpeg"
    raise UploadValidationError(
        "unsupported_document",
        "The document must be a valid PDF, PNG, or JPEG file.",
        status_code=415,
    )


def _validate_image(data: bytes, media_type: DocumentMediaType) -> tuple[int, int, int]:
    try:
        with Image.open(BytesIO(data)) as image:
            image_format = image.format
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                raise UploadValidationError(
                    "image_too_large",
                    f"Decoded images must not exceed {MAX_IMAGE_PIXELS} pixels.",
                    status_code=413,
                )
            image.load()
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as exc:
        raise UploadValidationError(
            "malformed_document",
            "The image could not be decoded safely.",
        ) from exc

    expected_format = "PNG" if media_type == "image/png" else "JPEG"
    if image_format != expected_format:
        raise UploadValidationError(
            "signature_mismatch",
            "The document signature does not match its encoded format.",
            status_code=415,
        )
    return 1, width, height


def _validate_pdf(data: bytes) -> int:
    try:
        document = pymupdf.open(stream=data, filetype="pdf")
    except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
        raise UploadValidationError(
            "malformed_document",
            "The PDF could not be decoded safely.",
        ) from exc

    try:
        if document.is_encrypted or getattr(document, "is_repaired", False):
            raise UploadValidationError(
                "unsupported_pdf",
                "Encrypted or repaired PDFs are not supported.",
            )
        page_count = int(document.page_count)
        if page_count < 1:
            raise UploadValidationError("empty_document", "The PDF has no pages.")
        if page_count > MAX_PDF_PAGES:
            raise UploadValidationError(
                "too_many_pages",
                f"PDF uploads must not exceed {MAX_PDF_PAGES} pages.",
                status_code=413,
            )
        document_pixels = 0
        for page_number in range(page_count):
            rectangle = document.load_page(page_number).rect
            width = math.ceil(rectangle.width * PDF_RENDER_DPI / 72)
            height = math.ceil(rectangle.height * PDF_RENDER_DPI / 72)
            page_pixels = width * height
            if width <= 0 or height <= 0 or page_pixels > MAX_IMAGE_PIXELS:
                raise UploadValidationError(
                    "page_too_large",
                    f"Rendered PDF pages must not exceed {MAX_IMAGE_PIXELS} pixels.",
                    status_code=413,
                )
            document_pixels += page_pixels
            if document_pixels > MAX_DOCUMENT_PIXELS:
                raise UploadValidationError(
                    "document_too_large",
                    "The rendered PDF exceeds the total pixel limit.",
                    status_code=413,
                )
    finally:
        document.close()
    return page_count
