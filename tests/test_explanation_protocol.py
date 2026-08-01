"""Explanation provider boundary tests."""

import pytest
from pydantic import ValidationError

from veridoc.explanation.protocol import ExplanationDraft, ExplanationRequest
from veridoc.verification.models import VerificationFinding, VerificationResult


def test_explanation_request_copies_verified_findings_into_an_immutable_tuple() -> None:
    finding = VerificationFinding(
        finding_type="duplicate_invoice_number",
        severity="high",
        explanation="This vendor already has an invoice with the extracted invoice number.",
        comparison_source="invoice_register",
        deterministic_rule="invoice_number must be unique within a vendor history",
    )
    verification = VerificationResult(findings=[finding])

    request = ExplanationRequest.from_verification(verification)

    assert request.findings == (finding,)
    assert isinstance(request.findings, tuple)


def test_explanation_draft_is_strict_and_uses_a_nonnegative_finding_index() -> None:
    draft = ExplanationDraft(finding_index=0, narrative="Review this invoice number.")

    assert draft.finding_index == 0
    with pytest.raises(ValidationError):
        ExplanationDraft(finding_index=-1, narrative="Invalid index.")
    with pytest.raises(ValidationError):
        ExplanationDraft(finding_index=0, narrative="Draft.", unexpected="value")
