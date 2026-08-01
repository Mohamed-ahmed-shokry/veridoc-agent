"""Structured invoice extraction contract tests."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from veridoc.extraction.models import (
    EvidenceReference,
    ExtractionUncertainty,
    InvoiceExtraction,
    InvoiceLineItem,
)


def test_invoice_extraction_preserves_optional_values_and_evidence() -> None:
    extraction = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies Ltd.",
        invoice_number="INV-001",
        invoice_date="2026-08-01",
        currency="USD",
        total="18400.00",
        line_items=[
            InvoiceLineItem(
                description="Fictional consulting",
                quantity="2",
                unit_price="9200.00",
                total_price="18400.00",
                evidence=[EvidenceReference(page_number=1, source="ocr_text")],
            )
        ],
        ocr_confidence=91.5,
        extraction_confidence=82.0,
        evidence={
            "invoice_number": [
                EvidenceReference(
                    page_number=1,
                    source="ocr_text",
                    text_span="Invoice No: INV-001",
                )
            ]
        },
        uncertainties=[
            ExtractionUncertainty(
                field="due_date", reason="No due date was visible in the document."
            )
        ],
    )

    assert extraction.invoice_date == date(2026, 8, 1)
    assert extraction.total == Decimal("18400.00")
    assert extraction.vendor_identifier is None
    assert extraction.line_items[0].quantity == Decimal(2)


def test_invoice_extraction_rejects_invalid_confidence_evidence_and_extra_fields() -> (
    None
):
    with pytest.raises(ValidationError):
        InvoiceExtraction(document_type="invoice", currency="usd")
    with pytest.raises(ValidationError):
        InvoiceExtraction(document_type="invoice", extraction_confidence=101)
    with pytest.raises(ValidationError):
        EvidenceReference(page_number=0, source="page_image")
    with pytest.raises(ValidationError):
        InvoiceExtraction(document_type="invoice", unexpected="value")
