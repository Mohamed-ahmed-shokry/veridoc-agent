"""FastAPI application construction tests."""

import httpx
import pytest
from fastapi import FastAPI

from veridoc.__main__ import main
from veridoc.app import app


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


def test_application_object_imports_with_expected_metadata() -> None:
    """The installed package exposes a configured FastAPI application."""
    assert isinstance(app, FastAPI)
    assert app.title == "Veridoc"
    assert app.version == "0.1.0"


def test_console_launcher_starts_the_documented_local_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def fake_run(app_target: str, **kwargs: object) -> None:
        observed["app_target"] = app_target
        observed.update(kwargs)

    monkeypatch.setattr("veridoc.__main__.uvicorn.run", fake_run)

    main()

    assert observed == {
        "app_target": "veridoc.app:app",
        "host": "127.0.0.1",
        "port": 8000,
    }


@pytest.mark.anyio
async def test_unknown_route_returns_safe_not_found_response() -> None:
    """Unknown paths use FastAPI's small JSON 404 response."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/not-a-route")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
