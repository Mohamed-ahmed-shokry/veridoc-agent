"""Upload validation ordering tests for external dependency construction."""

from __future__ import annotations

from io import BytesIO
from threading import get_ident

import httpx
import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image
from starlette.datastructures import Headers

from veridoc.app import (
    app,
    get_ocr_engine,
    get_processing_service,
    get_structured_extractor,
    get_validated_upload,
)
from veridoc.ingestion.models import ValidatedUpload
from veridoc.ingestion.validation import UploadValidationError


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (12, 8), color="white").save(output, format="PNG")
    return output.getvalue()


@pytest.mark.anyio
async def test_upload_validation_runs_off_loop_and_closes_the_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loop_thread = get_ident()
    validation_thread: int | None = None
    payload = _png_bytes()

    def reject_upload(
        data: bytes,
        *,
        filename: str | None,
        declared_content_type: str | None,
    ) -> ValidatedUpload:
        nonlocal validation_thread
        validation_thread = get_ident()
        assert data == payload
        assert filename == "invoice.png"
        assert declared_content_type == "image/png"
        raise UploadValidationError(
            "synthetic_rejection",
            "The synthetic upload was rejected.",
            status_code=415,
        )

    monkeypatch.setattr("veridoc.ingestion.dependencies.validate_upload", reject_upload)
    backing_file = BytesIO(payload)
    upload = UploadFile(
        backing_file,
        filename="invoice.png",
        headers=Headers({"content-type": "image/png"}),
    )

    with pytest.raises(HTTPException) as captured:
        await get_validated_upload(upload)

    assert captured.value.status_code == 415
    assert captured.value.detail == {
        "code": "synthetic_rejection",
        "message": "The synthetic upload was rejected.",
    }
    assert validation_thread is not None
    assert validation_thread != loop_thread
    assert backing_file.closed is True


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("path", "dependencies"),
    [
        ("/ocr", (get_ocr_engine,)),
        ("/extract", (get_ocr_engine, get_structured_extractor)),
        ("/process", (get_processing_service,)),
    ],
)
async def test_invalid_uploads_are_rejected_before_external_dependencies(
    path: str,
    dependencies: tuple[object, ...],
) -> None:
    resolved_dependencies: list[str] = []

    def unexpected_dependency() -> None:
        resolved_dependencies.append(path)

    for dependency in dependencies:
        app.dependency_overrides[dependency] = unexpected_dependency
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.post(
                path,
                files={"file": ("invoice.png", _png_bytes(), "text/plain")},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "unsupported_content_type"
    assert resolved_dependencies == []
