"""In-process tests for the Phase 1 OCR endpoint."""

from __future__ import annotations

from io import BytesIO
from threading import get_ident
from typing import Any

import httpx
import pytest
from PIL import Image

from veridoc.app import app, get_ocr_engine
from veridoc.ocr.models import OCRPageResult
from veridoc.ocr.protocol import OCRUnavailableError


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (12, 8), color="white").save(output, format="PNG")
    return output.getvalue()


class _FakeEngine:
    def __init__(self) -> None:
        self.thread_id: int | None = None

    def recognize(self, image: Image.Image) -> OCRPageResult:
        assert image.mode == "RGB"
        self.thread_id = get_ident()
        return OCRPageResult(text="Fictional Vendor Invoice INV-001", confidence=91.0)


class _UnavailableEngine:
    def recognize(self, image: Image.Image) -> OCRPageResult:
        del image
        raise OCRUnavailableError


async def _post_file(engine: Any, *, content_type: str = "image/png") -> httpx.Response:
    app.dependency_overrides[get_ocr_engine] = lambda: engine
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.post(
                "/ocr",
                files={"file": ("fictional-invoice.png", _png_bytes(), content_type)},
            )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_ocr_endpoint_returns_raw_text_and_confidence() -> None:
    event_loop_thread = get_ident()
    engine = _FakeEngine()
    response = await _post_file(engine)

    assert response.status_code == 200
    assert response.json() == {
        "media_type": "image/png",
        "text": "Fictional Vendor Invoice INV-001",
        "confidence": 91.0,
        "pages": [
            {
                "page_number": 1,
                "text": "Fictional Vendor Invoice INV-001",
                "confidence": 91.0,
            }
        ],
    }
    assert engine.thread_id is not None
    assert engine.thread_id != event_loop_thread


@pytest.mark.anyio
async def test_ocr_endpoint_rejects_declared_type_mismatch() -> None:
    response = await _post_file(_FakeEngine(), content_type="application/pdf")

    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "content_type_mismatch"


@pytest.mark.anyio
async def test_ocr_endpoint_reports_unavailable_engine_safely() -> None:
    response = await _post_file(_UnavailableEngine())

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "ocr_unavailable",
            "message": "OCR is not available on this server.",
        }
    }


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/ocr", "/extract", "/process"])
async def test_document_endpoints_report_invalid_ocr_configuration_safely(
    path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TESSERACT_LANG", "eng")
    monkeypatch.setenv("TESSERACT_TIMEOUT_SECONDS", "not-a-number")
    request_id = "invalid-ocr-configuration"
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            path,
            files={"file": ("fictional-invoice.png", _png_bytes(), "image/png")},
            headers={"X-Request-ID": request_id},
        )

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "ocr_unavailable",
            "message": "OCR is not available on this server.",
        }
    }
    assert response.headers["X-Request-ID"] == request_id
