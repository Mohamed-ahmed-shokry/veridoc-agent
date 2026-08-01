"""Bounded validation for invoice upload streams."""

from typing import Final, Protocol, cast

from veridoc.ingestion.models import SupportedMediaType, UploadedDocument

MAX_UPLOAD_BYTES: Final = 10 * 1024 * 1024
READ_CHUNK_BYTES: Final = 64 * 1024
SUPPORTED_MEDIA_TYPES: Final = frozenset(
    {"application/pdf", "image/jpeg", "image/png"}
)


class DocumentValidationError(ValueError):
    """Raised when an uploaded invoice is unsafe or unsupported."""


class AsyncReadableUpload(Protocol):
    """The subset of an HTTP upload needed by the validator."""

    filename: str | None
    content_type: str | None

    async def read(self, size: int = -1) -> bytes:
        """Read up to ``size`` bytes from the upload stream."""


async def read_validated_upload(upload: AsyncReadableUpload) -> UploadedDocument:
    """Read, bound, and verify a PDF, PNG, or JPEG invoice upload."""
    declared_type = upload.content_type
    if declared_type not in SUPPORTED_MEDIA_TYPES:
        raise DocumentValidationError("Only PDF, PNG, and JPEG invoice files are supported.")

    content = await _read_bounded(upload)
    _validate_content_signature(content, declared_type)

    return UploadedDocument(
        filename=upload.filename or "invoice",
        media_type=cast(SupportedMediaType, declared_type),
        content=content,
    )


async def _read_bounded(upload: AsyncReadableUpload) -> bytes:
    """Read an upload stream without exceeding the configured size limit."""
    chunks: list[bytes] = []
    total_bytes = 0

    while chunk := await upload.read(READ_CHUNK_BYTES):
        total_bytes += len(chunk)
        if total_bytes > MAX_UPLOAD_BYTES:
            raise DocumentValidationError(
                f"Invoice files must not exceed {MAX_UPLOAD_BYTES} bytes."
            )
        chunks.append(chunk)

    if total_bytes == 0:
        raise DocumentValidationError("Invoice files must not be empty.")

    return b"".join(chunks)


def _validate_content_signature(content: bytes, media_type: str) -> None:
    """Reject payloads whose bytes do not match their declared media type."""
    signatures = {
        "application/pdf": b"%PDF-",
        "image/jpeg": b"\xff\xd8\xff",
        "image/png": b"\x89PNG\r\n\x1a\n",
    }
    if not content.startswith(signatures[media_type]):
        raise DocumentValidationError(
            "The uploaded file contents do not match its declared media type."
        )
