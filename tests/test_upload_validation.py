"""Invoice upload validation tests."""

import pytest

from veridoc.ingestion.validation import (
    MAX_UPLOAD_BYTES,
    DocumentValidationError,
    read_validated_upload,
)


class FakeUpload:
    """A deterministic async upload stream for validator tests."""

    def __init__(self, content: bytes, content_type: str | None) -> None:
        self.content_type = content_type
        self.filename = "invoice"
        self._content = content

    async def read(self, size: int = -1) -> bytes:
        """Return the remaining fixture bytes in bounded chunks."""
        if not self._content:
            return b""
        chunk, self._content = self._content[:size], self._content[size:]
        return chunk


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


@pytest.mark.anyio
async def test_accepts_pdf_with_matching_content_signature() -> None:
    """PDF bytes with a PDF content type are retained for later decoding."""
    content = b"%PDF-1.7\nsynthetic invoice"

    document = await read_validated_upload(FakeUpload(content, "application/pdf"))

    assert document.content == content
    assert document.media_type == "application/pdf"


@pytest.mark.anyio
async def test_rejects_mismatched_content_signature() -> None:
    """A declared image cannot bypass validation with arbitrary bytes."""
    with pytest.raises(DocumentValidationError, match="do not match"):
        await read_validated_upload(FakeUpload(b"not an image", "image/png"))


@pytest.mark.anyio
async def test_rejects_streams_larger_than_upload_limit() -> None:
    """Streaming validation stops as soon as an upload exceeds the limit."""
    content = b"%PDF-" + (b"x" * MAX_UPLOAD_BYTES)

    with pytest.raises(DocumentValidationError, match="must not exceed"):
        await read_validated_upload(FakeUpload(content, "application/pdf"))
