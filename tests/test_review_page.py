"""Minimal review-interface route tests."""

import httpx
import pytest

from veridoc.app import app


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


@pytest.mark.anyio
async def test_review_page_submits_to_process_and_renders_without_html_injection() -> (
    None
):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/review")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'id="invoice-file"' in response.text
    assert 'fetch("/process"' in response.text
    assert "textContent" in response.text
