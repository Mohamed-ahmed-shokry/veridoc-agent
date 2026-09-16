"""Scan-before-decode upload wiring tests."""

from __future__ import annotations

from io import BytesIO

import httpx
import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image
from starlette.datastructures import Headers

from veridoc.app import app, get_validated_upload
from veridoc.ingestion.models import UndecodedUpload
from veridoc.scanning.protocol import (
    ScanRejectedError,
    ScanResult,
    ScanUnavailableError,
)
from veridoc.scanning.service import scan_upload_bytes


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (12, 8), color="white").save(output, format="PNG")
    return output.getvalue()


def _upload(payload: bytes) -> UploadFile:
    return UploadFile(
        BytesIO(payload),
        filename="invoice.png",
        headers=Headers({"content-type": "image/png"}),
    )


def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "VERIDOC_SCAN_ENABLED",
        "VERIDOC_CLAMD_HOST",
        "VERIDOC_CLAMD_PORT",
        "VERIDOC_CLAMD_TIMEOUT_SECONDS",
        "VERIDOC_QUARANTINE_DIRECTORY",
        "VERIDOC_QUARANTINE_RETENTION_DAYS",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.anyio
async def test_disabled_scanning_leaves_uploads_untouched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With scanning disabled the dependency returns the decoded upload."""
    _clean_environment(monkeypatch)

    upload = await get_validated_upload(_upload(_png_bytes()))

    assert upload.media_type == "image/png"
    assert upload.page_count == 1


@pytest.mark.anyio
async def test_scanning_runs_between_signature_check_and_decode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The scan observes signature-checked bytes before decoding starts."""
    _clean_environment(monkeypatch)
    events: list[str] = []
    payload = _png_bytes()

    async def record_scan(
        data: bytes, *, filename: str | None, declared_content_type: str | None
    ) -> None:
        events.append("scan")
        assert data == payload
        assert filename == "invoice.png"
        assert declared_content_type == "image/png"

    def record_decode(pending: UndecodedUpload):
        events.append("decode")
        assert pending.data == payload
        raise AssertionError("decode must run after the scan")

    monkeypatch.setattr("veridoc.ingestion.dependencies.scan_upload_bytes", record_scan)
    monkeypatch.setattr(
        "veridoc.ingestion.dependencies.decode_validated_upload", record_decode
    )

    with pytest.raises(AssertionError, match="decode must run after the scan"):
        await get_validated_upload(_upload(payload))

    assert events == ["scan", "decode"]


@pytest.mark.anyio
async def test_invalid_uploads_never_reach_the_scanner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Signature failures reject before any scanner work is attempted."""
    _clean_environment(monkeypatch)
    scanned: list[bytes] = []

    async def record_scan(data: bytes, **kwargs: object) -> None:
        scanned.append(data)

    monkeypatch.setattr("veridoc.ingestion.dependencies.scan_upload_bytes", record_scan)

    with pytest.raises(HTTPException) as captured:
        await get_validated_upload(
            UploadFile(
                BytesIO(_png_bytes()),
                filename="invoice.png",
                headers=Headers({"content-type": "text/plain"}),
            )
        )

    assert captured.value.status_code == 415
    assert scanned == []


@pytest.mark.anyio
async def test_scan_rejection_maps_to_a_safe_422(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A positive scan rejects the upload with the typed 422 contract."""

    async def reject_scan(data: bytes, **kwargs: object) -> None:
        raise ScanRejectedError

    monkeypatch.setattr("veridoc.ingestion.dependencies.scan_upload_bytes", reject_scan)

    with pytest.raises(HTTPException) as captured:
        await get_validated_upload(_upload(_png_bytes()))

    assert captured.value.status_code == 422
    assert captured.value.detail == {
        "code": "document_scan_rejected",
        "message": "The uploaded document was rejected by malware scanning.",
    }


@pytest.mark.anyio
async def test_scan_outage_maps_to_a_safe_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A scanner failure fails closed with the typed 503 contract."""

    async def fail_scan(data: bytes, **kwargs: object) -> None:
        raise ScanUnavailableError

    monkeypatch.setattr("veridoc.ingestion.dependencies.scan_upload_bytes", fail_scan)

    with pytest.raises(HTTPException) as captured:
        await get_validated_upload(_upload(_png_bytes()))

    assert captured.value.status_code == 503
    assert captured.value.detail == {
        "code": "document_scan_unavailable",
        "message": "Document scanning is not available on this server.",
    }


@pytest.mark.anyio
async def test_scan_service_is_a_noop_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The orchestration returns immediately without resolving a scanner."""
    _clean_environment(monkeypatch)
    constructed: list[str] = []
    monkeypatch.setattr(
        "veridoc.scanning.service.ClamAVScanner",
        lambda settings: constructed.append("scanner"),
    )

    await scan_upload_bytes(
        b"bytes", filename="invoice.png", declared_content_type="image/png"
    )

    assert constructed == []


@pytest.mark.anyio
async def test_scan_service_quarantines_positives_then_rejects(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """A positive scan stores the bytes and raises the rejection error."""
    monkeypatch.setenv("VERIDOC_SCAN_ENABLED", "1")
    monkeypatch.setenv("VERIDOC_QUARANTINE_DIRECTORY", str(tmp_path))

    class PositiveScanner:
        def __init__(self, settings) -> None:
            del settings

        async def scan(self, data: bytes) -> ScanResult:
            assert data == b"malicious-bytes"
            return ScanResult(
                clean=False, engine="clamav", signature="Eicar-Test-Signature"
            )

    monkeypatch.setattr("veridoc.scanning.service.ClamAVScanner", PositiveScanner)

    with pytest.raises(ScanRejectedError):
        await scan_upload_bytes(
            b"malicious-bytes",
            filename="invoice.pdf",
            declared_content_type="application/pdf",
        )

    quarantine_files = list((tmp_path / "objects").iterdir())
    assert len(quarantine_files) == 1
    assert quarantine_files[0].read_bytes() == b"malicious-bytes"


@pytest.mark.anyio
async def test_scan_service_passes_clean_uploads(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """A clean scan stores nothing and raises nothing."""
    monkeypatch.setenv("VERIDOC_SCAN_ENABLED", "1")
    monkeypatch.setenv("VERIDOC_QUARANTINE_DIRECTORY", str(tmp_path))

    class CleanScanner:
        def __init__(self, settings) -> None:
            del settings

        async def scan(self, data: bytes) -> ScanResult:
            return ScanResult(clean=True, engine="clamav")

    monkeypatch.setattr("veridoc.scanning.service.ClamAVScanner", CleanScanner)

    await scan_upload_bytes(
        b"clean-bytes",
        filename="invoice.png",
        declared_content_type="image/png",
    )

    assert list((tmp_path / "objects").iterdir()) == []


@pytest.mark.anyio
async def test_scan_service_fails_closed_on_scanner_outage(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """A scanner failure propagates without quarantining anything."""
    monkeypatch.setenv("VERIDOC_SCAN_ENABLED", "1")
    monkeypatch.setenv("VERIDOC_QUARANTINE_DIRECTORY", str(tmp_path))

    class BrokenScanner:
        def __init__(self, settings) -> None:
            del settings

        async def scan(self, data: bytes) -> ScanResult:
            raise ScanUnavailableError

    monkeypatch.setattr("veridoc.scanning.service.ClamAVScanner", BrokenScanner)

    with pytest.raises(ScanUnavailableError):
        await scan_upload_bytes(
            b"bytes", filename="invoice.png", declared_content_type="image/png"
        )

    assert list((tmp_path / "objects").iterdir()) == []


@pytest.mark.anyio
async def test_ocr_route_rejects_scan_positives_before_ocr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /ocr maps a positive scan to 422 without touching OCR."""
    from veridoc.app import get_ocr_engine

    async def reject_scan(data: bytes, **kwargs: object) -> None:
        raise ScanRejectedError

    def unexpected_engine():
        raise AssertionError("OCR must not resolve after a scan rejection")

    monkeypatch.setattr("veridoc.ingestion.dependencies.scan_upload_bytes", reject_scan)
    app.dependency_overrides[get_ocr_engine] = unexpected_engine
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.post(
                "/ocr",
                files={"file": ("invoice.png", _png_bytes(), "image/png")},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "code": "document_scan_rejected",
            "message": "The uploaded document was rejected by malware scanning.",
        }
    }
