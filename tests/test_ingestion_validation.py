"""Focused upload validation tests."""

from __future__ import annotations

from io import BytesIO

import fitz
import pytest
from PIL import Image

from veridoc.ingestion.validation import (
    MAX_DOCUMENT_PIXELS,
    MAX_IMAGE_PIXELS,
    MAX_PDF_PAGES,
    MAX_UPLOAD_BYTES,
    UploadValidationError,
    read_bounded_upload,
    sanitize_filename,
    validate_upload,
)


def _png_bytes(size: tuple[int, int] = (8, 4)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, color="white").save(output, format="PNG")
    return output.getvalue()


def _pdf_bytes(page_count: int = 1) -> bytes:
    document = fitz.open()
    for index in range(page_count):
        page = document.new_page(width=72, height=72)
        page.insert_text((8, 24), f"Fictional Vendor Invoice INV-{index + 1:03d}")
    data = document.tobytes()
    document.close()
    return data


def test_png_is_validated_by_signature_and_dimensions() -> None:
    validated = validate_upload(
        _png_bytes(),
        filename=r"..\private/invoice.png",
        declared_content_type="image/png; charset=binary",
    )

    assert validated.media_type == "image/png"
    assert validated.filename == "invoice.png"
    assert (validated.width, validated.height, validated.page_count) == (8, 4, 1)


def test_pdf_is_validated_and_page_count_is_recorded() -> None:
    validated = validate_upload(
        _pdf_bytes(2),
        filename="invoice.pdf",
        declared_content_type="application/pdf",
    )

    assert validated.media_type == "application/pdf"
    assert validated.page_count == 2
    assert validated.width is None


def test_filename_normalization_removes_paths_and_controls() -> None:
    filename = "C:\\temp\\bad name" + chr(0) + ".pdf"
    assert sanitize_filename(filename) == "bad_name.pdf"
    assert sanitize_filename(None) == "upload"


def test_content_type_mismatch_is_rejected() -> None:
    with pytest.raises(UploadValidationError, match="declared content type") as error:
        validate_upload(
            _png_bytes(),
            filename="invoice.pdf",
            declared_content_type="application/pdf",
        )

    assert error.value.code == "content_type_mismatch"
    assert error.value.status_code == 415


def test_malformed_signature_is_rejected() -> None:
    with pytest.raises(UploadValidationError) as error:
        validate_upload(
            b"not a document", filename="invoice.txt", declared_content_type=None
        )

    assert error.value.code == "unsupported_document"
    assert error.value.status_code == 415


def test_image_pixel_limit_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _png_bytes((3, 2))
    monkeypatch.setattr("veridoc.ingestion.validation.MAX_IMAGE_PIXELS", 4)
    load_called = False

    def unexpected_load(self: Image.Image, *args: object, **kwargs: object) -> None:
        del self, args, kwargs
        nonlocal load_called
        load_called = True
        raise AssertionError("oversized images must be rejected before decoding")

    monkeypatch.setattr(Image.Image, "load", unexpected_load)

    with pytest.raises(UploadValidationError) as error:
        validate_upload(payload, filename="invoice.png", declared_content_type=None)

    assert error.value.code == "image_too_large"
    assert not load_called
    assert MAX_IMAGE_PIXELS > 4


def test_pdf_page_limit_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("veridoc.ingestion.validation.MAX_PDF_PAGES", 1)

    with pytest.raises(UploadValidationError) as error:
        validate_upload(
            _pdf_bytes(2), filename="invoice.pdf", declared_content_type=None
        )

    assert error.value.code == "too_many_pages"
    assert MAX_PDF_PAGES > 1


def test_pdf_document_pixel_limit_is_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("veridoc.ingestion.validation.MAX_DOCUMENT_PIXELS", 30_000)

    with pytest.raises(UploadValidationError) as error:
        validate_upload(
            _pdf_bytes(2), filename="invoice.pdf", declared_content_type=None
        )

    assert error.value.code == "document_too_large"
    assert error.value.status_code == 413
    assert MAX_DOCUMENT_PIXELS > 30_000


class _ChunkedUpload:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = iter(chunks)

    async def read(self, size: int) -> bytes:
        del size
        return next(self._chunks, b"")


@pytest.mark.anyio
async def test_streaming_read_rejects_oversized_upload() -> None:
    upload = _ChunkedUpload([b"a" * MAX_UPLOAD_BYTES, b"b"])

    with pytest.raises(UploadValidationError) as error:
        await read_bounded_upload(upload)  # type: ignore[arg-type]

    assert error.value.code == "upload_too_large"
    assert error.value.status_code == 413
