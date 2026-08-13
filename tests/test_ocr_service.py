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


class _InvalidConfidenceEngine:
    def __init__(self, confidence: float) -> None:
        self._confidence = confidence

    def recognize(self, image: Image.Image) -> OCRPageResult:
        del image
        return OCRPageResult(text="fictional page", confidence=self._confidence)


class _MalformedEngine:
    def recognize(self, image: Image.Image) -> object:
        del image
        return None


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


@pytest.mark.parametrize("confidence", [float("nan"), -1.0, 101.0])
def test_service_discards_invalid_adapter_confidence(confidence: float) -> None:
    upload = validate_upload(
        _png_bytes(),
        filename="fictional-invoice.png",
        declared_content_type="image/png",
    )

    result = OCRService(_InvalidConfidenceEngine(confidence)).process(upload)

    assert result.pages == (OCRPageResult(text="fictional page", confidence=None),)
    assert result.confidence is None


def test_service_rejects_malformed_adapter_results() -> None:
    upload = validate_upload(
        _png_bytes(),
        filename="fictional-invoice.png",
        declared_content_type="image/png",
    )

    with pytest.raises(OCRProcessingError):
        OCRService(_MalformedEngine()).process(upload)


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
    monkeypatch.setattr(
        "veridoc.ocr.service._encode_png",
        lambda image, *, max_bytes: b"x" * 6,
    )
    engine = _FakeEngine()
    upload = validate_upload(
        _pdf_bytes(2),
        filename="fictional-invoice.pdf",
        declared_content_type="application/pdf",
    )

    with pytest.raises(OCRProcessingError):
        OCRService(engine).process_with_page_images(upload)

    assert engine.calls == 1


def test_service_stops_png_encoding_at_the_remaining_byte_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upload = validate_upload(
        _png_bytes(),
        filename="fictional-invoice.png",
        declared_content_type="image/png",
    )
    output: BytesIO | None = None

    class ChunkWritingImage:
        closed = False

        def save(self, destination: BytesIO, *, format: str) -> None:
            nonlocal output
            assert format == "PNG"
            output = destination
            destination.write(b"a" * 6)
            destination.write(b"b" * 6)

        def close(self) -> None:
            self.closed = True

    image = ChunkWritingImage()
    monkeypatch.setattr("veridoc.ocr.service.MAX_PAGE_IMAGE_BUNDLE_BYTES", 10)
    monkeypatch.setattr(
        "veridoc.ocr.service._iter_page_images",
        lambda path, media_type: iter((image,)),
    )
    engine = _FakeEngine()

    with pytest.raises(OCRProcessingError):
        OCRService(engine).process_with_page_images(upload)

    assert engine.calls == 0
    assert image.closed is True
    assert output is not None
    assert output.getvalue() == b"a" * 6
