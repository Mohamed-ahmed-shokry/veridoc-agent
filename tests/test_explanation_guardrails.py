"""Contradiction-protection tests for provider explanation drafts."""

from veridoc.explanation.guardrails import validated_narratives
from veridoc.explanation.protocol import (
    ExplanationDraft,
    ExplanationDraftResult,
    ExplanationRequest,
)
from veridoc.verification.models import VerificationFinding, VerificationResult


def _request() -> ExplanationRequest:
    return ExplanationRequest.from_verification(
        VerificationResult(
            findings=[
                VerificationFinding(
                    finding_type="historical_total_outlier",
                    severity="high",
                    explanation="The invoice total is outside the vendor's established range.",
                    comparison_source="vendor_history",
                    deterministic_rule="absolute_z_score >= 3",
                    observed_value="18400.00",
                    expected_range=("5600.00", "8800.00"),
                ),
                VerificationFinding(
                    finding_type="duplicate_invoice_number",
                    severity="high",
                    explanation="This vendor already has an invoice with the extracted invoice number.",
                    comparison_source="invoice_register",
                    deterministic_rule="invoice_number must be unique within a vendor history",
                ),
            ]
        )
    )


def test_guardrails_accept_complete_nonfactual_guidance_in_finding_order() -> None:
    drafts = ExplanationDraftResult(
        drafts=[
            ExplanationDraft(
                finding_index=1,
                narrative="Review the documented finding with the responsible team.",
            ),
            ExplanationDraft(
                finding_index=0,
                narrative="Confirm the supplied evidence before taking action.",
            ),
        ]
    )

    assert validated_narratives(_request(), drafts) == [
        "Confirm the supplied evidence before taking action.",
        "Review the documented finding with the responsible team.",
    ]


def test_guardrails_reject_incomplete_numeric_or_comparative_provider_claims() -> None:
    request = _request()

    assert (
        validated_narratives(
            request,
            ExplanationDraftResult(
                drafts=[
                    ExplanationDraft(finding_index=0, narrative="Review the finding.")
                ]
            ),
        )
        is None
    )
    assert (
        validated_narratives(
            request,
            ExplanationDraftResult(
                drafts=[
                    ExplanationDraft(
                        finding_index=0,
                        narrative="The amount is 18400.00 and needs review.",
                    ),
                    ExplanationDraft(finding_index=1, narrative="Review the finding."),
                ]
            ),
        )
        is None
    )
    assert (
        validated_narratives(
            request,
            ExplanationDraftResult(
                drafts=[
                    ExplanationDraft(
                        finding_index=0,
                        narrative="The amount is above the expected range.",
                    ),
                    ExplanationDraft(finding_index=1, narrative="Review the finding."),
                ]
            ),
        )
        is None
    )
