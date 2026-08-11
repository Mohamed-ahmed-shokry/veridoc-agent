"""Upload validation ordering tests for external dependency construction."""

from __future__ import annotations

from io import BytesIO

import httpx
import pytest
from PIL import Image

from veridoc.app import (
    app,
    get_ocr_engine,
    get_processing_service,
    get_structured_extractor,
)


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (12, 8), color="white").save(output, format="PNG")
    return output.getvalue()


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
