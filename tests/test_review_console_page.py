"""Structural safety tests for the authenticated review console shell."""

import httpx
import pytest

from veridoc.app import app


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


@pytest.mark.anyio
async def test_console_page_renders_login_and_session_controls_safely() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/review/console")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    body = response.text
    assert 'id="login-form"' in body
    assert 'id="credential"' in body
    assert 'type="password"' in body
    assert 'id="logout-button"' in body
    assert 'fetch("/review/session"' in body
    assert "innerHTML" not in body
    assert "textContent" in body
