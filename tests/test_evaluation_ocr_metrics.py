"""Tests for OCR Character and Word Error Rate metrics."""

from __future__ import annotations

from veridoc.evaluation.metrics.ocr import (
    aggregate_ocr_metrics,
    compute_cer,
    compute_wer,
    levenshtein_distance,
)


def test_levenshtein_distance_cases() -> None:
    assert levenshtein_distance("", "") == 0
    assert levenshtein_distance("abc", "abc") == 0
    assert levenshtein_distance("", "abc") == 3
    assert levenshtein_distance("abc", "") == 3
    assert levenshtein_distance("kitten", "sitting") == 3
    assert levenshtein_distance(["the", "quick", "fox"], ["the", "brown", "fox"]) == 1


def test_compute_cer() -> None:
    assert compute_cer("hello", "hello") == 0.0
    assert compute_cer("", "") == 0.0
    assert compute_cer("", "abc") == 1.0
    # "helo" vs "hello": 1 insertion, ref len 4 -> 0.25
    assert compute_cer("helo", "hello") == 0.25


def test_compute_wer() -> None:
    assert compute_wer("the quick brown fox", "the quick brown fox") == 0.0
    assert compute_wer("", "") == 0.0
    assert compute_wer("", "word") == 1.0
    # 1 substitution out of 4 words -> 0.25
    assert compute_wer("the quick brown fox", "the fast brown fox") == 0.25


def test_aggregate_ocr_metrics() -> None:
    pairs = [
        ("INVOICE #100", "INVOICE #100"),  # exact match
        ("Total: $500", "Total: $50"),  # 1 deletion in 11 chars, 1 word edit in 2 words
    ]
    metrics = aggregate_ocr_metrics(pairs)
    assert metrics.character_count == 12 + 11
    assert metrics.word_count == 2 + 2
    assert metrics.character_errors == 1
    assert metrics.word_errors == 1
    assert metrics.cer == round(1 / 23, 4)
    assert metrics.wer == round(1 / 4, 4)


def test_aggregate_ocr_metrics_empty() -> None:
    metrics = aggregate_ocr_metrics([])
    assert metrics.character_count == 0
    assert metrics.word_count == 0
    assert metrics.cer == 0.0
    assert metrics.wer == 0.0
