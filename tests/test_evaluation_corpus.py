"""Benchmark corpus validity tests for slice minimums and ground truth."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pymupdf
import pytest
from PIL import Image

from veridoc.evaluation.manifest import load_corpus_manifest
from veridoc.evaluation.models import (
    CorpusManifest,
    EvaluationThresholds,
    GroundTruthInvoice,
)
from veridoc.ingestion.validation import validate_upload

_CORPUS_ROOT = Path(__file__).resolve().parent / "fixtures" / "corpus"


@pytest.fixture(scope="module")
def manifest() -> CorpusManifest:
    """Load the benchmark manifest with integrity verification."""
    loaded, _ = load_corpus_manifest(
        _CORPUS_ROOT / "manifest.json", verify_integrity=True
    )
    return loaded


@pytest.fixture(scope="module")
def ground_truths(
    manifest: CorpusManifest,
) -> dict[str, GroundTruthInvoice]:
    """Load every ground truth file bound by the manifest."""
    _, gt_map = load_corpus_manifest(
        _CORPUS_ROOT / "manifest.json", verify_integrity=True
    )
    return gt_map


def test_corpus_manifest_verifies_integrity(manifest: CorpusManifest) -> None:
    """Every manifest file and ground truth digest verifies."""
    assert manifest.corpus_name == "veridoc-synthetic-benchmark-v2"
    assert len(manifest.documents) == 20


def test_every_slice_meets_the_preregistered_minimum(
    manifest: CorpusManifest,
) -> None:
    """Each slice value holds at least the preregistered sample count."""
    minimum = EvaluationThresholds().min_slice_sample_count
    counts: Counter[str] = Counter()
    for document in manifest.documents:
        counts[f"language={document.language}"] += 1
        counts[f"quality={document.quality}"] += 1
        counts[f"layout={document.layout}"] += 1
        counts[
            "page_count=multi" if document.page_count >= 2 else "page_count=single"
        ] += 1

    assert len(counts) == 8
    short = {slice: count for slice, count in counts.items() if count < minimum}
    assert not short, f"Slices below the minimum of {minimum}: {short}"


def test_document_identifiers_paths_and_bytes_are_unique(
    manifest: CorpusManifest,
) -> None:
    """No duplicated identifiers, paths, or exact file bytes (leakage)."""
    assert len({doc.document_id for doc in manifest.documents}) == len(
        manifest.documents
    )
    assert len({doc.file_path for doc in manifest.documents}) == len(manifest.documents)
    assert len({doc.file_sha256 for doc in manifest.documents}) == len(
        manifest.documents
    )
    assert len({doc.ground_truth_sha256 for doc in manifest.documents}) == len(
        manifest.documents
    )


def test_ground_truth_invoice_numbers_are_unique(
    ground_truths: dict[str, GroundTruthInvoice],
) -> None:
    """Every corpus invoice carries a distinct invoice number."""
    numbers = [gt.invoice_number for gt in ground_truths.values()]
    assert None not in numbers
    assert len(set(numbers)) == len(numbers)


def test_ground_truth_arithmetic_matches_expected_verdicts(
    ground_truths: dict[str, GroundTruthInvoice],
) -> None:
    """Subtotal/tax/total consistency agrees with the expected verdict."""
    for document_id, gt in sorted(ground_truths.items()):
        for item in gt.line_items:
            assert item.quantity * item.unit_price == item.total_amount, document_id
        if gt.subtotal_amount is None:
            assert gt.expected_finding_types == [], document_id
            assert gt.expected_verdict == "clear", document_id
            continue
        assert gt.tax_amount is not None, document_id
        items_total = sum(item.total_amount for item in gt.line_items)
        if gt.line_items:
            assert items_total == gt.subtotal_amount, document_id
        consistent = gt.subtotal_amount + gt.tax_amount == gt.total_amount
        if consistent:
            assert gt.expected_finding_types == [], document_id
            assert gt.expected_verdict == "clear", document_id
        else:
            assert gt.expected_finding_types == ["invoice_total_mismatch"], document_id
            assert gt.expected_verdict == "review_required", document_id


def test_transcripts_cover_invoice_number_and_total(
    ground_truths: dict[str, GroundTruthInvoice],
) -> None:
    """Every OCR transcript contains its invoice number and total amount."""
    for document_id, gt in sorted(ground_truths.items()):
        assert gt.ocr_transcript, document_id
        assert gt.invoice_number in gt.ocr_transcript, document_id
        assert str(gt.total_amount) in gt.ocr_transcript, document_id


def test_manifest_page_counts_match_decoded_documents(
    manifest: CorpusManifest,
) -> None:
    """Manifest page counts agree with the actual decoded documents."""
    for document in manifest.documents:
        path = _CORPUS_ROOT / document.file_path
        if path.suffix == ".png":
            with Image.open(path):
                assert document.page_count == 1, document.document_id
        else:
            with pymupdf.open(path) as pdf:
                assert document.page_count == pdf.page_count, document.document_id


def test_every_document_passes_ingestion_validation(
    manifest: CorpusManifest,
) -> None:
    """Every corpus file is a processable bounded upload of its mime type."""
    for document in manifest.documents:
        path = _CORPUS_ROOT / document.file_path
        upload = validate_upload(
            path.read_bytes(), filename=path.name, declared_content_type=None
        )
        assert upload.media_type == document.mime_type, document.document_id
        assert upload.page_count == document.page_count, document.document_id


def test_mime_types_match_file_signatures(manifest: CorpusManifest) -> None:
    """Manifest mime types agree with the leading file signature bytes."""
    for document in manifest.documents:
        data = (_CORPUS_ROOT / document.file_path).read_bytes()
        if document.mime_type == "image/png":
            assert data.startswith(b"\x89PNG\r\n\x1a\n"), document.document_id
        else:
            assert data.startswith(b"%PDF-"), document.document_id


def test_amounts_use_at_most_two_decimal_places(
    ground_truths: dict[str, GroundTruthInvoice],
) -> None:
    """Corpus amounts stay within two decimal places like real invoices."""
    for document_id, gt in sorted(ground_truths.items()):
        assert gt.total_amount is not None, document_id
        amounts = [
            gt.total_amount,
            gt.subtotal_amount,
            gt.tax_amount,
            *(item.total_amount for item in gt.line_items),
            *(item.unit_price for item in gt.line_items),
        ]
        for amount in amounts:
            if amount is None:
                continue
            assert -amount.as_tuple().exponent <= 2, (document_id, amount)
