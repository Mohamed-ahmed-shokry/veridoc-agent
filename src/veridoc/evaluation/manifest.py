"""Corpus manifest loading, integrity verification, and provenance checking."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final

from veridoc.evaluation.models import CorpusDocument, CorpusManifest, GroundTruthInvoice

ALLOWED_LICENSES: Final[frozenset[str]] = frozenset(
    {
        "synthetic",
        "public-licensed",
        "proprietary-governed",
    }
)

_CHUNK_SIZE: Final[int] = 64 * 1024


class CorpusManifestError(Exception):
    """Base exception for corpus manifest errors."""


class CorpusIntegrityError(CorpusManifestError):
    """Raised when file existence or SHA-256 digest fails verification."""


class CorpusProvenanceError(CorpusManifestError):
    """Raised when document license or provenance policy is violated."""


def compute_file_sha256(path: Path) -> str:
    """Compute the SHA-256 digest of a file in streaming chunks."""
    hasher = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()


def validate_document_provenance(
    document: CorpusDocument,
    *,
    allowed_licenses: frozenset[str] = ALLOWED_LICENSES,
) -> None:
    """Verify that a document satisfies license and provenance safety policy."""
    normalized_license = document.license.strip().lower()
    if normalized_license not in allowed_licenses:
        raise CorpusProvenanceError(
            f"Document '{document.document_id}' has disallowed license '{document.license}'. "
            f"Allowed licenses: {sorted(allowed_licenses)}"
        )
    if not document.provenance or not document.provenance.strip():
        raise CorpusProvenanceError(
            f"Document '{document.document_id}' has empty provenance description."
        )


def load_corpus_manifest(
    manifest_path: Path,
    *,
    verify_integrity: bool = True,
) -> tuple[CorpusManifest, dict[str, GroundTruthInvoice]]:
    """Load and validate a corpus manifest and its associated ground truth invoices.

    Returns the parsed CorpusManifest and a dictionary mapping document_id to
    GroundTruthInvoice.
    """
    if not manifest_path.is_file():
        raise CorpusIntegrityError(f"Corpus manifest file not found: {manifest_path}")

    try:
        raw_text = manifest_path.read_text(encoding="utf-8")
        manifest = CorpusManifest.model_validate_json(raw_text)
    except Exception as exc:
        raise CorpusManifestError(
            f"Failed to parse corpus manifest at {manifest_path}: {exc}"
        ) from exc

    corpus_root = manifest_path.parent
    ground_truth_map: dict[str, GroundTruthInvoice] = {}

    for doc in manifest.documents:
        validate_document_provenance(doc)

        doc_file = corpus_root / doc.file_path
        gt_file = corpus_root / doc.ground_truth_path

        if not doc_file.is_file():
            raise CorpusIntegrityError(
                f"Document file missing for '{doc.document_id}': {doc_file}"
            )
        if not gt_file.is_file():
            raise CorpusIntegrityError(
                f"Ground truth file missing for '{doc.document_id}': {gt_file}"
            )

        if verify_integrity:
            actual_doc_sha = compute_file_sha256(doc_file)
            if actual_doc_sha != doc.file_sha256:
                raise CorpusIntegrityError(
                    f"SHA-256 mismatch for document file '{doc.document_id}': "
                    f"expected {doc.file_sha256}, got {actual_doc_sha}"
                )

            actual_gt_sha = compute_file_sha256(gt_file)
            if actual_gt_sha != doc.ground_truth_sha256:
                raise CorpusIntegrityError(
                    f"SHA-256 mismatch for ground truth file '{doc.document_id}': "
                    f"expected {doc.ground_truth_sha256}, got {actual_gt_sha}"
                )

        try:
            gt_text = gt_file.read_text(encoding="utf-8")
            gt_invoice = GroundTruthInvoice.model_validate_json(gt_text)
        except Exception as exc:
            raise CorpusManifestError(
                f"Failed to parse ground truth invoice for '{doc.document_id}' at {gt_file}: {exc}"
            ) from exc

        ground_truth_map[doc.document_id] = gt_invoice

    return manifest, ground_truth_map
