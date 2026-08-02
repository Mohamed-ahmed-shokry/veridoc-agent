"""Strict final processing result contract tests."""

import pytest
from pydantic import ValidationError

from veridoc.extraction.models import EvidenceReference, InvoiceExtraction
from veridoc.processing.models import ProcessingResult, ProcessingVerdict


def test_processing_result_preserves_extracted_evidence() -> None:
    result = ProcessingResult(
        extraction=InvoiceExtraction(
            document_type="invoice",
            evidence={
                "invoice_number": [
                    EvidenceReference(
                        page_number=1,
                        source="ocr_text",
                        text_span="Invoice No: INV-001",
                    )
                ]
            },
        ),
        verdict=ProcessingVerdict(
            status="clear",
            summary="No deterministic verification findings require review.",
            finding_count=0,
        ),
    )

    assert (
        result.extraction.evidence["invoice_number"][0].text_span
        == "Invoice No: INV-001"
    )
    assert result.findings == []
    assert result.explanations == []


def test_processing_verdict_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ProcessingVerdict(
            status="clear",
            summary="No deterministic verification findings require review.",
            finding_count=0,
            unsupported=True,
        )
