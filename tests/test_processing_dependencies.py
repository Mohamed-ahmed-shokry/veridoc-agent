"""Processing dependency composition tests."""

import pytest

from veridoc.app import get_explanation_service, get_invoice_repository
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
