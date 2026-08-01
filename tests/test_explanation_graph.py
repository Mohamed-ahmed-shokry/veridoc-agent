"""Explanation graph composition tests."""

import pytest

from veridoc.explanation.graph import build_explanation_graph
from veridoc.explanation.service import ExplanationService
from veridoc.verification.models import VerificationFinding, VerificationResult


@pytest.mark.anyio
async def test_explanation_graph_runs_the_service_node() -> None:
    graph = build_explanation_graph(ExplanationService())
    verification = VerificationResult(
        findings=[
            VerificationFinding(
                finding_type="duplicate_invoice_number",
                severity="high",
                explanation="This vendor already has an invoice with the extracted invoice number.",
                comparison_source="invoice_register",
                deterministic_rule="invoice_number must be unique within a vendor history",
            )
        ]
    )

    result = await graph.ainvoke({"verification": verification})

    assert result["verification"] == verification
    assert result["explanations"].explanations[0].source == "deterministic"
