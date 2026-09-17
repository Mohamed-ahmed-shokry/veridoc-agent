"""Tests for corpus manifest loading, integrity verification, and provenance checking."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from veridoc.evaluation.manifest import (
    CorpusIntegrityError,
    CorpusManifestError,
    CorpusProvenanceError,
    compute_file_sha256,
    load_corpus_manifest,
    validate_document_provenance,
)
from veridoc.evaluation.models import (
    CorpusDocument,
    GroundTruthInvoice,
    GroundTruthLineItem,
)


def test_compute_file_sha256(tmp_path: Path) -> None:
    test_file = tmp_path / "test.txt"
    content = b"Hello, Veridoc evaluation!"
    test_file.write_bytes(content)
    expected_hash = hashlib.sha256(content).hexdigest()
    assert compute_file_sha256(test_file) == expected_hash


def test_validate_document_provenance() -> None:
    valid_doc = CorpusDocument(
        document_id="doc-001",
        file_path="doc.pdf",
        file_sha256="a" * 64,
        mime_type="application/pdf",
        page_count=1,
        license="synthetic",
        provenance="synthetic generator v1",
        language="eng",
        quality="clean",
        layout="standard",
        ground_truth_path="gt.json",
        ground_truth_sha256="a" * 64,
    )
    validate_document_provenance(valid_doc)

    disallowed_license_doc = CorpusDocument(
        document_id="doc-002",
        file_path="doc.pdf",
        file_sha256="a" * 64,
        mime_type="application/pdf",
        page_count=1,
        license="proprietary-governed",
        provenance="production dump",
        language="eng",
        quality="clean",
        layout="standard",
        ground_truth_path="gt.json",
        ground_truth_sha256="a" * 64,
    )
    with pytest.raises(CorpusProvenanceError, match="disallowed license"):
        validate_document_provenance(
            disallowed_license_doc,
            allowed_licenses=frozenset({"synthetic"}),
        )

    empty_provenance_doc = CorpusDocument(
        document_id="doc-003",
        file_path="doc.pdf",
        file_sha256="a" * 64,
        mime_type="application/pdf",
        page_count=1,
        license="synthetic",
        provenance="   ",
        language="eng",
        quality="clean",
        layout="standard",
        ground_truth_path="gt.json",
        ground_truth_sha256="a" * 64,
    )
    with pytest.raises(CorpusProvenanceError, match="empty provenance"):
        validate_document_provenance(empty_provenance_doc)


def test_load_corpus_manifest_success(tmp_path: Path) -> None:
    doc_content = b"%PDF-1.4 fictional invoice content"
    doc_path = tmp_path / "invoices" / "inv1.pdf"
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_bytes(doc_content)
    doc_sha = hashlib.sha256(doc_content).hexdigest()

    gt_invoice = GroundTruthInvoice(
        invoice_number="INV-100",
        invoice_date="2026-03-01",
        due_date=None,
        vendor_name="Acme Inc",
        vendor_tax_id=None,
        currency="USD",
        total_amount=Decimal("100.00"),
        subtotal_amount=None,
        tax_amount=None,
        line_items=[
            GroundTruthLineItem(
                description="Consulting",
                quantity=Decimal(1),
                unit_price=Decimal("100.00"),
                total_amount=Decimal("100.00"),
            )
        ],
        expected_finding_types=[],
        expected_verdict="clear",
        ocr_transcript="Invoice INV-100 Acme Inc $100.00",
    )
    gt_bytes = gt_invoice.model_dump_json(indent=2).encode("utf-8")
    gt_path = tmp_path / "ground_truth" / "inv1.json"
    gt_path.parent.mkdir(parents=True, exist_ok=True)
    gt_path.write_bytes(gt_bytes)
    gt_sha = hashlib.sha256(gt_bytes).hexdigest()

    manifest_data = {
        "corpus_name": "Test Benchmark",
        "description": "Benchmark for evaluation",
        "documents": [
            {
                "document_id": "inv-001",
                "file_path": "invoices/inv1.pdf",
                "file_sha256": doc_sha,
                "mime_type": "application/pdf",
                "page_count": 1,
                "license": "synthetic",
                "provenance": "synthetic-v1",
                "language": "eng",
                "quality": "clean",
                "layout": "standard",
                "ground_truth_path": "ground_truth/inv1.json",
                "ground_truth_sha256": gt_sha,
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    manifest, gt_map = load_corpus_manifest(manifest_path)
    assert manifest.corpus_name == "Test Benchmark"
    assert len(manifest.documents) == 1
    assert "inv-001" in gt_map
    assert gt_map["inv-001"].invoice_number == "INV-100"


def test_load_corpus_manifest_missing_manifest(tmp_path: Path) -> None:
    with pytest.raises(CorpusIntegrityError, match="not found"):
        load_corpus_manifest(tmp_path / "nonexistent.json")


def test_load_corpus_manifest_corrupted_json(tmp_path: Path) -> None:
    bad_manifest = tmp_path / "bad.json"
    bad_manifest.write_text("invalid json {", encoding="utf-8")
    with pytest.raises(CorpusManifestError, match="Failed to parse"):
        load_corpus_manifest(bad_manifest)


def test_load_corpus_manifest_missing_files(tmp_path: Path) -> None:
    manifest_data = {
        "corpus_name": "Test Benchmark",
        "description": "Benchmark",
        "documents": [
            {
                "document_id": "inv-001",
                "file_path": "invoices/missing.pdf",
                "file_sha256": "a" * 64,
                "mime_type": "application/pdf",
                "page_count": 1,
                "license": "synthetic",
                "provenance": "synthetic-v1",
                "language": "eng",
                "quality": "clean",
                "layout": "standard",
                "ground_truth_path": "ground_truth/missing.json",
                "ground_truth_sha256": "b" * 64,
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    with pytest.raises(CorpusIntegrityError, match="Document file missing"):
        load_corpus_manifest(manifest_path)


def test_load_corpus_manifest_hash_mismatch(tmp_path: Path) -> None:
    doc_path = tmp_path / "doc.pdf"
    doc_path.write_bytes(b"content")
    gt_path = tmp_path / "gt.json"
    gt_path.write_text("{}", encoding="utf-8")

    manifest_data = {
        "corpus_name": "Test Benchmark",
        "description": "Benchmark",
        "documents": [
            {
                "document_id": "inv-001",
                "file_path": "doc.pdf",
                "file_sha256": "f" * 64,  # wrong hash
                "mime_type": "application/pdf",
                "page_count": 1,
                "license": "synthetic",
                "provenance": "synthetic-v1",
                "language": "eng",
                "quality": "clean",
                "layout": "standard",
                "ground_truth_path": "gt.json",
                "ground_truth_sha256": hashlib.sha256(b"{}").hexdigest(),
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")

    with pytest.raises(
        CorpusIntegrityError, match="SHA-256 mismatch for document file"
    ):
        load_corpus_manifest(manifest_path)
