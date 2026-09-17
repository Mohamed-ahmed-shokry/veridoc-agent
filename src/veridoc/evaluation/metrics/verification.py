"""Verification accuracy, confusion matrix, and verdict concordance metrics."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from veridoc.evaluation.models import GroundTruthInvoice, VerificationMetrics
from veridoc.verification.models import VerificationFinding

ALL_FINDING_TYPES: Final[frozenset[str]] = frozenset(
    {
        "invoice_total_mismatch",
        "line_item_amount_mismatch",
        "line_items_subtotal_mismatch",
        "invoice_date_after_due_date",
        "purchase_order_mismatch",
        "duplicate_invoice_number",
        "historical_total_outlier",
        "historical_line_item_price_outlier",
        "historical_line_item_quantity_outlier",
        "new_line_item",
        "rare_line_item",
        "payment_terms_changed",
        "missing_historical_field",
        "insufficient_history",
    }
)


def evaluate_verification_case(
    observed_findings: Sequence[VerificationFinding],
    observed_verdict: str,
    ground_truth: GroundTruthInvoice,
    all_rules: frozenset[str] = ALL_FINDING_TYPES,
) -> tuple[int, int, int, int, bool]:
    """Evaluate observed findings and verdict against ground truth.

    Returns:
        (tp, tn, fp, fn, verdict_concordant)
    """
    observed_types = {f.finding_type for f in observed_findings}
    expected_types = set(ground_truth.expected_finding_types)

    tp = len(observed_types & expected_types)
    fp = len(observed_types - expected_types)
    fn = len(expected_types - observed_types)

    # True negatives are evaluated rules that were neither observed nor expected
    tn = len(all_rules - (observed_types | expected_types))

    verdict_concordant = (
        observed_verdict.strip().lower()
        == ground_truth.expected_verdict.strip().lower()
    )

    return tp, tn, fp, fn, verdict_concordant


def aggregate_verification_metrics(
    cases: Sequence[tuple[Sequence[VerificationFinding], str, GroundTruthInvoice]],
    all_rules: frozenset[str] = ALL_FINDING_TYPES,
) -> VerificationMetrics:
    """Aggregate TPR, TNR, FPR, FNR, and verdict concordance across cases."""
    total_tp = 0
    total_tn = 0
    total_fp = 0
    total_fn = 0
    concordant_verdicts = 0
    total_cases = len(cases)

    for findings, verdict, gt in cases:
        tp, tn, fp, fn, concordant = evaluate_verification_case(
            findings, verdict, gt, all_rules=all_rules
        )
        total_tp += tp
        total_tn += tn
        total_fp += fp
        total_fn += fn
        if concordant:
            concordant_verdicts += 1

    total_positives = total_tp + total_fn
    total_negatives = total_tn + total_fp
    rules_evaluated = total_positives + total_negatives

    tpr = total_tp / total_positives if total_positives > 0 else 1.0
    tnr = total_tn / total_negatives if total_negatives > 0 else 1.0
    fpr = total_fp / total_negatives if total_negatives > 0 else 0.0
    fnr = total_fn / total_positives if total_positives > 0 else 0.0
    concordance = concordant_verdicts / total_cases if total_cases > 0 else 1.0

    return VerificationMetrics(
        rules_evaluated=rules_evaluated,
        true_positives=total_tp,
        true_negatives=total_tn,
        false_positives=total_fp,
        false_negatives=total_fn,
        tpr=round(tpr, 4),
        tnr=round(tnr, 4),
        fpr=round(fpr, 4),
        fnr=round(fnr, 4),
        verdict_concordance=round(concordance, 4),
    )
