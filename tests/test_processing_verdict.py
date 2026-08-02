"""Deterministic final verdict tests."""

from veridoc.processing.verdict import derive_verdict
from veridoc.verification.models import VerificationFinding, VerificationResult


def test_verdict_is_clear_only_when_there_are_no_findings() -> None:
    verdict = derive_verdict(VerificationResult())

    assert verdict.status == "clear"
    assert verdict.finding_count == 0
    assert verdict.highest_severity is None


def test_verdict_requires_review_and_reports_the_highest_severity() -> None:
    verdict = derive_verdict(
        VerificationResult(
            findings=[
                VerificationFinding(
                    finding_type="insufficient_history",
                    severity="info",
                    explanation="Not enough history is available.",
                    comparison_source="vendor_history",
                    deterministic_rule="history must contain three observations",
                ),
                VerificationFinding(
                    finding_type="duplicate_invoice_number",
                    severity="high",
                    explanation="The invoice number already exists for this vendor.",
                    comparison_source="invoice_register",
                    deterministic_rule="invoice_number must be unique within vendor history",
                ),
            ]
        )
    )

    assert verdict.status == "review_required"
    assert verdict.finding_count == 2
    assert verdict.highest_severity == "high"
