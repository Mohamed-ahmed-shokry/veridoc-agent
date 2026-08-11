"""Focused upload validation tests."""

from __future__ import annotations

from io import BytesIO

import pymupdf
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


def _jpeg_bytes(size: tuple[int, int] = (8, 4)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, color="white").save(output, format="JPEG")
    return output.getvalue()


def _pdf_bytes(page_count: int = 1) -> bytes:
    document = pymupdf.open()
    for index in range(page_count):
        page = document.new_page(width=72, height=72)
        page.insert_text((8, 24), f"Fictional Vendor Invoice INV-{index + 1:03d}")
    data = document.tobytes()
    document.close()
    return data


def _encrypted_pdf_bytes() -> bytes:
    document = pymupdf.open()
    document.new_page(width=72, height=72)
    data = document.tobytes(
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="fictional-owner",
        user_pw="fictional-user",
    )
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


def test_jpeg_alias_is_validated_and_normalized() -> None:
    validated = validate_upload(
        _jpeg_bytes(),
        filename=r"..\private/fictional invoice.jpeg",
        declared_content_type="image/jpg",
    )

    assert validated.media_type == "image/jpeg"
    assert validated.suffix == ".jpg"
    assert validated.filename == "fictional_invoice.jpeg"
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


@pytest.mark.parametrize(
    ("payload", "content_type", "message"),
    [
        (
            b"\x89PNG\r\n\x1a\ntruncated",
            "image/png",
            "The image could not be decoded safely.",
        ),
        (
            b"%PDF-1.7\ntruncated",
            "application/pdf",
            "The PDF could not be decoded safely.",
        ),
    ],
)
def test_supported_signatures_with_undecodable_payloads_are_rejected_safely(
    payload: bytes,
    content_type: str,
    message: str,
) -> None:
    with pytest.raises(UploadValidationError) as error:
        validate_upload(
            payload,
            filename="fictional-invoice",
            declared_content_type=content_type,
        )

    assert error.value.code == "malformed_document"
    assert error.value.status_code == 400
    assert error.value.message == message
    assert str(error.value) == message


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


def test_encrypted_pdf_is_rejected_safely() -> None:
    with pytest.raises(UploadValidationError) as error:
        validate_upload(
            _encrypted_pdf_bytes(),
            filename="fictional-invoice.pdf",
            declared_content_type="application/pdf",
        )

    assert error.value.code == "unsupported_pdf"
    assert error.value.status_code == 400
    assert error.value.message == "Encrypted or repaired PDFs are not supported."


def test_pdf_page_pixel_limit_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("veridoc.ingestion.validation.MAX_IMAGE_PIXELS", 20_000)

    with pytest.raises(UploadValidationError) as error:
        validate_upload(
            _pdf_bytes(), filename="invoice.pdf", declared_content_type=None
        )

    assert error.value.code == "page_too_large"
    assert error.value.status_code == 413
    assert error.value.message == "Rendered PDF pages must not exceed 20000 pixels."
    assert MAX_IMAGE_PIXELS > 20_000


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


def test_pdf_page_decode_failure_is_rejected_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenDocument:
        is_encrypted = False
        is_repaired = False
        page_count = 1
        closed = False

        def load_page(self, page_number: int) -> None:
            del page_number
            raise RuntimeError("synthetic decoder detail")

        def close(self) -> None:
            self.closed = True

    document = BrokenDocument()
    monkeypatch.setattr(pymupdf, "open", lambda **kwargs: document)

    with pytest.raises(UploadValidationError) as error:
        validate_upload(
            b"%PDF-1.7\n",
            filename="invoice.pdf",
            declared_content_type="application/pdf",
        )

    assert error.value.code == "malformed_document"
    assert error.value.message == "The PDF could not be decoded safely."
    assert document.closed is True


def test_empty_pdf_is_rejected_and_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    class EmptyDocument:
        is_encrypted = False
        is_repaired = False
        page_count = 0
        closed = False

        def close(self) -> None:
            self.closed = True

    document = EmptyDocument()
    monkeypatch.setattr(pymupdf, "open", lambda **kwargs: document)

    with pytest.raises(UploadValidationError) as error:
        validate_upload(
            b"%PDF-1.7\n",
            filename="fictional-invoice.pdf",
            declared_content_type="application/pdf",
        )

    assert error.value.code == "empty_document"
    assert error.value.status_code == 400
    assert error.value.message == "The PDF has no pages."
    assert document.closed is True


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
