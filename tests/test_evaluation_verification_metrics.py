"""Tests for verification accuracy, verdict concordance, and explanation metrics."""

from __future__ import annotations

from decimal import Decimal

from veridoc.evaluation.metrics.explanation import (
    aggregate_explanation_metrics,
    detect_numerical_contradictions,
)
from veridoc.evaluation.metrics.verification import (
    aggregate_verification_metrics,
    evaluate_verification_case,
)
from veridoc.evaluation.models import GroundTruthInvoice
from veridoc.explanation.models import FindingExplanation
from veridoc.verification.models import VerificationFinding


def _make_finding(
    finding_type: str, observed: str = "100", expected: str = "90"
) -> VerificationFinding:
    return VerificationFinding(
        finding_type=finding_type,  # type: ignore[arg-type]
        severity="high",
        explanation=f"Finding for {finding_type}",
        comparison_source="invoice_fields",
        deterministic_rule="rule_check",
        observed_value=observed,
        expected_value=expected,
    )


def test_evaluate_verification_case_concordant() -> None:
    gt = GroundTruthInvoice(
        invoice_number="INV-001",
        invoice_date="2026-03-01",
        due_date=None,
        vendor_name="Acme",
        vendor_tax_id=None,
        currency="USD",
        total_amount=Decimal("100.00"),
        subtotal_amount=None,
        tax_amount=None,
        line_items=[],
        expected_finding_types=["invoice_total_mismatch"],
        expected_verdict="review_required",
        ocr_transcript="INV-001",
    )

    finding = _make_finding("invoice_total_mismatch")
    tp, tn, fp, fn, concordant = evaluate_verification_case(
        [finding], "review_required", gt
    )
    assert tp == 1
    assert fp == 0
    assert fn == 0
    assert tn == 13  # 14 - 1
    assert concordant is True


def test_evaluate_verification_case_discordant() -> None:
    gt = GroundTruthInvoice(
        invoice_number="INV-001",
        invoice_date="2026-03-01",
        due_date=None,
        vendor_name="Acme",
        vendor_tax_id=None,
        currency="USD",
        total_amount=Decimal("100.00"),
        subtotal_amount=None,
        tax_amount=None,
        line_items=[],
        expected_finding_types=[],
        expected_verdict="clear",
        ocr_transcript="INV-001",
    )

    # Observed unexpected finding and wrong verdict
    finding = _make_finding("line_item_amount_mismatch")
    tp, tn, fp, fn, concordant = evaluate_verification_case(
        [finding], "review_required", gt
    )
    assert tp == 0
    assert fp == 1
    assert fn == 0
    assert tn == 13
    assert concordant is False


def test_aggregate_verification_metrics() -> None:
    gt1 = GroundTruthInvoice(
        invoice_number="INV-001",
        invoice_date="2026-03-01",
        due_date=None,
        vendor_name="Acme",
        vendor_tax_id=None,
        currency="USD",
        total_amount=Decimal("100.00"),
        subtotal_amount=None,
        tax_amount=None,
        line_items=[],
        expected_finding_types=["invoice_total_mismatch"],
        expected_verdict="review_required",
        ocr_transcript="INV-001",
    )
    gt2 = GroundTruthInvoice(
        invoice_number="INV-002",
        invoice_date="2026-03-01",
        due_date=None,
        vendor_name="Acme",
        vendor_tax_id=None,
        currency="USD",
        total_amount=Decimal("100.00"),
        subtotal_amount=None,
        tax_amount=None,
        line_items=[],
        expected_finding_types=[],
        expected_verdict="clear",
        ocr_transcript="INV-002",
    )

    f1 = _make_finding("invoice_total_mismatch")
    cases = [
        ([f1], "review_required", gt1),
        ([], "clear", gt2),
    ]
    metrics = aggregate_verification_metrics(cases)
    assert metrics.true_positives == 1
    assert metrics.false_positives == 0
    assert metrics.false_negatives == 0
    assert metrics.tpr == 1.0
    assert metrics.fnr == 0.0
    assert metrics.verdict_concordance == 1.0


def test_detect_numerical_contradictions() -> None:
    finding = _make_finding(
        "invoice_total_mismatch", observed="100.00", expected="90.00"
    )
    valid_exp = FindingExplanation(
        finding=finding,
        narrative="The total is 100.00 instead of 90.00.",
        numerical_context="Observed total 100.00, expected 90.00.",
        source="llm",
    )
    assert detect_numerical_contradictions(valid_exp) is False

    contradictory_exp = FindingExplanation(
        finding=finding,
        narrative="The total is 999.00 instead of 90.00.",  # 999.00 is unauthorized
        numerical_context="Observed total 100.00, expected 90.00.",
        source="llm",
    )
    assert detect_numerical_contradictions(contradictory_exp) is True


def test_aggregate_explanation_metrics() -> None:
    finding = _make_finding(
        "invoice_total_mismatch", observed="100.00", expected="90.00"
    )
    exp1 = FindingExplanation(
        finding=finding,
        narrative="The total is 100.00 instead of 90.00.",
        numerical_context="Observed total 100.00, expected 90.00.",
        source="llm",
    )
    exp2 = FindingExplanation(
        finding=finding,
        narrative="Total mismatch observed.",
        numerical_context="Observed total 100.00, expected 90.00.",
        source="deterministic",
    )
    metrics = aggregate_explanation_metrics([exp1, exp2], rejected_drafts_count=1)
    assert metrics.total_explanations == 2
    assert metrics.guardrail_passes == 1
    assert metrics.guardrail_rejections == 1
    assert metrics.guardrail_pass_rate == 0.5
    assert metrics.fallback_invocations == 1
    assert metrics.numerical_contradictions == 0
