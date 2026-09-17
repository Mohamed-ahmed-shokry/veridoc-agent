"""Extraction precision, recall, F1, and evidence-grounding metrics."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from veridoc.evaluation.models import (
    ExtractionMetrics,
    GroundTruthInvoice,
    GroundTruthLineItem,
)
from veridoc.extraction.models import InvoiceExtraction, InvoiceLineItem


def _normalize_string(val: str | None) -> str | None:
    if val is None:
        return None
    cleaned = " ".join(val.strip().lower().split())
    return cleaned if cleaned else None


def _normalize_date(val: Any) -> str | None:
    if val is None:
        return None
    return str(val).strip()


def _normalize_decimal(val: Any) -> Decimal | None:
    if val is None:
        return None
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val))
    except (ArithmeticError, ValueError):
        return None


def _compare_values(extracted: Any, ground_truth: Any) -> bool:
    if extracted is None and ground_truth is None:
        return True
    if extracted is None or ground_truth is None:
        return False

    if isinstance(ground_truth, Decimal) or isinstance(extracted, Decimal):
        d_ex = _normalize_decimal(extracted)
        d_gt = _normalize_decimal(ground_truth)
        return d_ex is not None and d_gt is not None and d_ex == d_gt

    s_ex = _normalize_string(str(extracted))
    s_gt = _normalize_string(str(ground_truth))
    return s_ex == s_gt


def _match_line_items(
    extracted_items: list[InvoiceLineItem],
    gt_items: list[GroundTruthLineItem],
) -> tuple[int, int, int]:
    """Match extracted line items to ground truth line items.

    Returns (matches, total_extracted, total_ground_truth).
    """
    total_ex = len(extracted_items)
    total_gt = len(gt_items)
    if total_ex == 0 and total_gt == 0:
        return 0, 0, 0

    matched_gt_indices: set[int] = set()
    matches = 0

    for ex in extracted_items:
        best_gt_idx = None
        for idx, gt in enumerate(gt_items):
            if idx in matched_gt_indices:
                continue

            desc_match = (
                _normalize_string(ex.description) == _normalize_string(gt.description)
                if ex.description and gt.description
                else False
            )
            amount_match = _compare_values(ex.total_price, gt.total_amount)

            if desc_match or amount_match:
                best_gt_idx = idx
                break

        if best_gt_idx is not None:
            matched_gt_indices.add(best_gt_idx)
            matches += 1

    return matches, total_ex, total_gt


def evaluate_extraction_pair(
    extraction: InvoiceExtraction,
    ground_truth: GroundTruthInvoice,
) -> tuple[int, int, int, int, int, int, int, int]:
    """Evaluate a single extraction against its ground truth.

    Returns:
        (tp, fp, fn, exact_matches, line_item_matches, line_items_ex, line_items_gt, grounded_count)
    """
    fields_to_check = [
        ("invoice_number", extraction.invoice_number, ground_truth.invoice_number),
        (
            "invoice_date",
            _normalize_date(extraction.invoice_date),
            _normalize_date(ground_truth.invoice_date),
        ),
        (
            "due_date",
            _normalize_date(extraction.due_date),
            _normalize_date(ground_truth.due_date),
        ),
        ("vendor_name", extraction.vendor_name, ground_truth.vendor_name),
        ("vendor_identifier", extraction.vendor_identifier, ground_truth.vendor_tax_id),
        ("currency", extraction.currency, ground_truth.currency),
        ("total", extraction.total, ground_truth.total_amount),
        ("subtotal", extraction.subtotal, ground_truth.subtotal_amount),
        ("tax", extraction.tax, ground_truth.tax_amount),
    ]

    tp = 0
    fp = 0
    fn = 0
    exact_matches = 0
    grounded_count = 0
    extracted_field_count = 0

    for field_name, ex_val, gt_val in fields_to_check:
        if gt_val is not None and ex_val is not None:
            extracted_field_count += 1
            if _compare_values(ex_val, gt_val):
                tp += 1
                exact_matches += 1
            else:
                fp += 1
                fn += 1
        elif gt_val is not None and ex_val is None:
            fn += 1
        elif gt_val is None and ex_val is not None:
            extracted_field_count += 1
            fp += 1

        if ex_val is not None:
            field_evidence = extraction.evidence.get(field_name, [])
            if any(ev.page_number >= 1 for ev in field_evidence):
                grounded_count += 1

    li_matches, li_ex, li_gt = _match_line_items(
        extraction.line_items, ground_truth.line_items
    )

    for item in extraction.line_items:
        if item.evidence and any(ev.page_number >= 1 for ev in item.evidence):
            grounded_count += 1

    return (
        tp,
        fp,
        fn,
        exact_matches,
        li_matches,
        li_ex,
        li_gt,
        grounded_count,
    )


def aggregate_extraction_metrics(
    pairs: Sequence[tuple[InvoiceExtraction, GroundTruthInvoice]],
) -> ExtractionMetrics:
    """Aggregate extraction precision, recall, F1, line-item F1, and evidence grounding."""
    total_tp = 0
    total_fp = 0
    total_fn = 0
    total_exact = 0
    total_li_matches = 0
    total_li_ex = 0
    total_li_gt = 0
    total_grounded = 0
    total_extracted_elements = 0

    for extraction, ground_truth in pairs:
        tp, fp, fn, exact, li_m, li_ex, li_gt, grounded = evaluate_extraction_pair(
            extraction, ground_truth
        )
        total_tp += tp
        total_fp += fp
        total_fn += fn
        total_exact += exact
        total_li_matches += li_m
        total_li_ex += li_ex
        total_li_gt += li_gt
        total_grounded += grounded

        # Count total extracted items (header non-null + line items)
        non_null_headers = sum(
            1
            for v in [
                extraction.invoice_number,
                extraction.invoice_date,
                extraction.due_date,
                extraction.vendor_name,
                extraction.vendor_identifier,
                extraction.currency,
                extraction.total,
                extraction.subtotal,
                extraction.tax,
            ]
            if v is not None
        )
        total_extracted_elements += non_null_headers + len(extraction.line_items)

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 1.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 1.0
    f1 = (
        (2 * precision * recall) / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    li_prec = (
        total_li_matches / total_li_ex
        if total_li_ex > 0
        else (1.0 if total_li_gt == 0 else 0.0)
    )
    li_rec = total_li_matches / total_li_gt if total_li_gt > 0 else 1.0
    li_f1 = (
        (2 * li_prec * li_rec) / (li_prec + li_rec)
        if (li_prec + li_rec) > 0
        else (1.0 if total_li_ex == 0 and total_li_gt == 0 else 0.0)
    )

    grounded_rate = (
        total_grounded / total_extracted_elements
        if total_extracted_elements > 0
        else 1.0
    )

    return ExtractionMetrics(
        field_count=total_tp + total_fn,
        exact_match_count=total_exact,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        line_item_f1=round(li_f1, 4),
        grounded_evidence_rate=round(min(grounded_rate, 1.0), 4),
    )
