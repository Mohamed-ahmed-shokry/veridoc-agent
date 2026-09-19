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


def test_processing_result_holds_vendor_resolution() -> None:
    from veridoc.vendors.models import VendorResolutionResult

    resolution = VendorResolutionResult(
        resolved_vendor_id="vnd_001",
        canonical_key="acme-corp",
        legal_name="Acme Corporation Ltd",
        confidence="exact_tax",
        score=1.0,
        matched_attribute="tax_id:GB123456789",
        status="active",
    )
    result = ProcessingResult(
        extraction=InvoiceExtraction(document_type="invoice"),
        verdict=ProcessingVerdict(
            status="clear",
            summary="Clear",
            finding_count=0,
        ),
        vendor_resolution=resolution,
    )

    assert result.vendor_resolution is not None
    assert result.vendor_resolution.resolved_vendor_id == "vnd_001"
    assert result.vendor_resolution.confidence == "exact_tax"
