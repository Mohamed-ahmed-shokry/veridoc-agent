"""OCR service tests using fictional synthetic invoice pages."""

from __future__ import annotations

from io import BytesIO

import pymupdf
import pytest
from PIL import Image

from veridoc.ingestion.validation import validate_upload
from veridoc.ocr.models import OCRPageResult
from veridoc.ocr.protocol import OCRProcessingError
from veridoc.ocr.service import OCRService


def _png_bytes() -> bytes:
    output = BytesIO()
    image = Image.new("RGB", (48, 24), color="white")
    image.save(output, format="PNG")
    return output.getvalue()


def _pdf_bytes(page_count: int = 1) -> bytes:
    document = pymupdf.open()
    for index in range(page_count):
        page = document.new_page(width=72, height=72)
        page.insert_text((8, 24), f"Fictional Vendor Invoice INV-{index + 1:03d}")
    data = document.tobytes()
    document.close()
    return data


class _FakeEngine:
    def __init__(self) -> None:
        self.calls = 0

    def recognize(self, image: Image.Image) -> OCRPageResult:
        self.calls += 1
        assert image.mode == "RGB"
        return OCRPageResult(text=f"fictional page {self.calls}", confidence=90.0)


def test_service_decodes_raster_upload_and_returns_raw_text() -> None:
    engine = _FakeEngine()
    upload = validate_upload(
        _png_bytes(),
        filename="fictional-invoice.png",
        declared_content_type="image/png",
    )

    result = OCRService(engine).process(upload)

    assert engine.calls == 1
    assert result.text == "fictional page 1"
    assert result.confidence == 90.0


def test_service_rasterizes_each_pdf_page() -> None:
    engine = _FakeEngine()
    upload = validate_upload(
        _pdf_bytes(2),
        filename="fictional-invoice.pdf",
        declared_content_type="application/pdf",
    )

    result = OCRService(engine).process(upload)

    assert engine.calls == 2
    assert result.text == "fictional page 1\ffictional page 2"
    assert len(result.pages) == 2


def test_service_exposes_normalized_page_images_for_vision_extraction() -> None:
    engine = _FakeEngine()
    upload = validate_upload(
        _png_bytes(),
        filename="fictional-invoice.png",
        declared_content_type="image/png",
    )

    bundle = OCRService(engine).process_with_page_images(upload)

    assert bundle.document.text == "fictional page 1"
    assert [page.page_number for page in bundle.page_images] == [1]
    with Image.open(BytesIO(bundle.page_images[0].image_bytes)) as rendered:
        assert rendered.format == "PNG"
        assert rendered.mode == "RGB"


def test_service_bounds_the_normalized_page_image_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("veridoc.ocr.service.MAX_PAGE_IMAGE_BUNDLE_BYTES", 10)
    monkeypatch.setattr("veridoc.ocr.service._encode_png", lambda image: b"x" * 6)
    engine = _FakeEngine()
    upload = validate_upload(
        _pdf_bytes(2),
        filename="fictional-invoice.pdf",
        declared_content_type="application/pdf",
    )

    with pytest.raises(OCRProcessingError):
        OCRService(engine).process_with_page_images(upload)

    assert engine.calls == 1
