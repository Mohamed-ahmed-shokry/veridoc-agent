"""Health endpoint tests."""

import httpx
import pytest

from veridoc.app import app


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


@pytest.mark.anyio
async def test_health_check_returns_ok_status() -> None:
    """The health endpoint reports that the API is available."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_check_declares_typed_response_schema() -> None:
    """OpenAPI identifies the health response through its named schema."""
    openapi = app.openapi()
    response_schema = openapi["paths"]["/health"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]

    assert response_schema == {"$ref": "#/components/schemas/HealthResponse"}
    assert openapi["components"]["schemas"]["HealthResponse"]["required"] == ["status"]
