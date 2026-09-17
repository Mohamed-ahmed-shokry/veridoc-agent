"""OCR Character Error Rate (CER) and Word Error Rate (WER) evaluation metrics."""

from __future__ import annotations

from collections.abc import Sequence

from veridoc.evaluation.models import OCRMetrics


def levenshtein_distance[T](seq1: Sequence[T], seq2: Sequence[T]) -> int:
    """Compute standard Levenshtein distance between two sequences with O(M) space."""
    n = len(seq1)
    m = len(seq2)
    if n == 0:
        return m
    if m == 0:
        return n

    dp = list(range(m + 1))
    for i in range(1, n + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, m + 1):
            temp = dp[j]
            cost = 0 if seq1[i - 1] == seq2[j - 1] else 1
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + cost)
            prev = temp
    return dp[m]


def compute_cer(reference: str, hypothesis: str) -> float:
    """Compute Character Error Rate (CER) between reference and hypothesis text."""
    ref_chars = list(reference)
    hyp_chars = list(hypothesis)
    dist = levenshtein_distance(ref_chars, hyp_chars)
    if not ref_chars:
        return 0.0 if not hyp_chars else 1.0
    return dist / len(ref_chars)


def compute_wer(reference: str, hypothesis: str) -> float:
    """Compute Word Error Rate (WER) between reference and hypothesis text."""
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    dist = levenshtein_distance(ref_words, hyp_words)
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    return dist / len(ref_words)


def aggregate_ocr_metrics(pairs: Sequence[tuple[str, str]]) -> OCRMetrics:
    """Aggregate CER and WER over a sequence of (reference, hypothesis) text pairs."""
    total_chars = 0
    total_char_dist = 0
    total_words = 0
    total_word_dist = 0

    for ref, hyp in pairs:
        ref_chars = list(ref)
        hyp_chars = list(hyp)
        char_dist = levenshtein_distance(ref_chars, hyp_chars)
        total_chars += len(ref_chars)
        total_char_dist += char_dist

        ref_words = ref.split()
        hyp_words = hyp.split()
        word_dist = levenshtein_distance(ref_words, hyp_words)
        total_words += len(ref_words)
        total_word_dist += word_dist

    cer = round(total_char_dist / total_chars, 4) if total_chars > 0 else 0.0
    wer = round(total_word_dist / total_words, 4) if total_words > 0 else 0.0

    return OCRMetrics(
        character_count=total_chars,
        word_count=total_words,
        character_errors=total_char_dist,
        word_errors=total_word_dist,
        cer=cer,
        wer=wer,
    )
