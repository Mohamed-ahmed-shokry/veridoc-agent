"""Processing dependency composition tests."""

import pytest

from veridoc import app as app_module
from veridoc.app import (
    get_explanation_service,
    get_invoice_repository,
    get_structured_extractor,
)
from veridoc.extraction.config import OpenAIExtractionSettings
from veridoc.verification.models import VerificationFinding, VerificationResult


def test_reference_repository_uses_the_configured_local_path(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "reference-data.sqlite3"
    monkeypatch.setenv("VERIDOC_REFERENCE_DATABASE", str(database_path))

    repository = get_invoice_repository()

    assert database_path.exists()
    assert repository.list_vendor_invoices("fictional-supplies") == []


@pytest.mark.anyio
async def test_extraction_dependency_closes_its_request_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ClosableExtractor:
        def __init__(self, settings: OpenAIExtractionSettings) -> None:
            assert settings.model == "test-model"
            self.closed = False

        async def aclose(self) -> None:
            self.closed = True

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("VERIDOC_LLM_MODEL", "test-model")
    monkeypatch.setattr(app_module, "OpenAIResponsesExtractor", ClosableExtractor)
    dependency = get_structured_extractor()

    extractor = await anext(dependency)
    assert extractor.closed is False

    await dependency.aclose()

    assert extractor.closed is True


@pytest.mark.anyio
async def test_explanation_service_uses_deterministic_fallback_without_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("VERIDOC_LLM_MODEL", raising=False)

    result = await get_explanation_service().explain(
        VerificationResult(
            findings=[
                VerificationFinding(
                    finding_type="duplicate_invoice_number",
                    severity="high",
                    explanation="The invoice number already exists for this vendor.",
                    comparison_source="invoice_register",
                    deterministic_rule="invoice_number must be unique within vendor history",
                )
            ]
        )
    )

    assert result.explanations[0].source == "deterministic"
