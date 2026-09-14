"""Readiness probe tests."""

import httpx
import pytest

from veridoc.app import app
from veridoc.deployment.readiness import (
    ReadinessCheck,
    ReadinessResult,
    readiness_from_environment,
)


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


def test_readiness_is_at_least_live_with_default_environment() -> None:
    """A default local environment reports ready for every configured check."""
    result = readiness_from_environment({})
    assert result.ready is True
    assert result.as_dict() == {
        "reference_store": True,
        "review_store": True,
        "review_identity": True,
        "extraction_provider": True,
    }


def test_readiness_reports_configured_but_incomplete_extraction() -> None:
    """A half-configured extraction provider marks readiness failed."""
    result = readiness_from_environment({"OPENAI_API_KEY": "secret-key-value"})
    assert result.ready is False
    assert result.as_dict()["extraction_provider"] is False


def test_readiness_reports_half_configured_review_identity() -> None:
    """A review origin without an actor file marks readiness failed."""
    result = readiness_from_environment(
        {"VERIDOC_REVIEW_ORIGIN": "https://review.example"}
    )
    assert result.ready is False
    assert result.as_dict()["review_identity"] is False


def test_readiness_reports_missing_store_parent(tmp_path) -> None:
    """A configured store whose parent directory is absent is not ready."""
    result = readiness_from_environment(
        {"VERIDOC_REFERENCE_DATABASE": str(tmp_path / "missing" / "ref.sqlite3")}
    )
    assert result.ready is False
    assert result.as_dict()["reference_store"] is False


def test_readiness_reports_valid_actor_file(tmp_path) -> None:
    """A correctly configured actor file and origin marks readiness passing."""
    actor_file = tmp_path / "actors.json"
    actor_file.write_text(
        '[{"actor_id": "reviewer-1", "role": "reviewer", '
        '"secret_digest": "' + "a" * 64 + '"}]'
    )
    result = readiness_from_environment(
        {
            "VERIDOC_REVIEW_ACTORS_FILE": str(actor_file),
            "VERIDOC_REVIEW_ORIGIN": "https://review.example",
        }
    )
    assert result.ready is True
    assert result.as_dict()["review_identity"] is True


def test_readiness_check_and_result_are_frozen_dataclasses() -> None:
    """Readiness values are immutable and expose the plain mapping form."""
    result = readiness_from_environment({})
    assert isinstance(result, ReadinessResult)
    assert isinstance(result.checks[0], ReadinessCheck)
    assert result.as_dict() == {check.name: check.ok for check in result.checks}


@pytest.mark.anyio
async def test_ready_endpoint_reports_ready_on_default_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A working local environment returns a typed 200 readiness response."""
    for name in (
        "OPENAI_API_KEY",
        "VERIDOC_LLM_MODEL",
        "VERIDOC_REVIEW_ACTORS_FILE",
        "VERIDOC_REVIEW_ORIGIN",
        "VERIDOC_REFERENCE_DATABASE",
        "VERIDOC_REVIEW_DATABASE",
    ):
        monkeypatch.delenv(name, raising=False)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["reference_store"] is True


@pytest.mark.anyio
async def test_ready_endpoint_returns_safe_503_when_dependency_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing configured dependency maps to a safe 503 with the checks."""
    monkeypatch.setenv("OPENAI_API_KEY", "secret-key-value")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body == {
        "status": "not_ready",
        "checks": {
            "reference_store": True,
            "review_store": True,
            "review_identity": True,
            "extraction_provider": False,
        },
    }


def test_ready_endpoint_declares_typed_response_schema() -> None:
    """OpenAPI identifies the readiness response through its named schema."""
    openapi = app.openapi()
    response_schema = openapi["paths"]["/ready"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert response_schema == {"$ref": "#/components/schemas/ReadyResponse"}
    assert openapi["components"]["schemas"]["ReadyResponse"]["required"] == [
        "status",
        "checks",
    ]
