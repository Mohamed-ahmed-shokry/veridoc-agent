"""Tests for extraction precision, recall, F1, line-item, and evidence-grounding metrics."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from veridoc.evaluation.metrics.extraction import (
    aggregate_extraction_metrics,
    evaluate_extraction_pair,
)
from veridoc.evaluation.models import GroundTruthInvoice, GroundTruthLineItem
from veridoc.extraction.models import (
    EvidenceReference,
    InvoiceExtraction,
    InvoiceLineItem,
)


def test_evaluate_extraction_pair_perfect() -> None:
    gt = GroundTruthInvoice(
        invoice_number="INV-001",
        invoice_date="2026-03-01",
        due_date="2026-03-31",
        vendor_name="Acme Corp",
        vendor_tax_id="12345",
        currency="USD",
        total_amount=Decimal("115.00"),
        subtotal_amount=Decimal("100.00"),
        tax_amount=Decimal("15.00"),
        line_items=[
            GroundTruthLineItem(
                description="Consulting",
                quantity=Decimal(2),
                unit_price=Decimal("50.00"),
                total_amount=Decimal("100.00"),
            )
        ],
        expected_finding_types=[],
        expected_verdict="clear",
        ocr_transcript="INV-001 Acme Corp $115.00",
    )

    extraction = InvoiceExtraction(
        document_type="invoice",
        invoice_number="inv-001",  # case-insensitive match
        invoice_date=date(2026, 3, 1),
        due_date=date(2026, 3, 31),
        vendor_name="Acme Corp",
        vendor_identifier="12345",
        currency="USD",
        total=Decimal("115.00"),
        subtotal=Decimal("100.00"),
        tax=Decimal("15.00"),
        line_items=[
            InvoiceLineItem(
                description="Consulting",
                quantity=Decimal(2),
                unit_price=Decimal("50.00"),
                total_price=Decimal("100.00"),
                evidence=[EvidenceReference(page_number=1, source="ocr_text")],
            )
        ],
        evidence={
            "invoice_number": [EvidenceReference(page_number=1, source="ocr_text")],
            "invoice_date": [EvidenceReference(page_number=1, source="ocr_text")],
            "due_date": [EvidenceReference(page_number=1, source="ocr_text")],
            "vendor_name": [EvidenceReference(page_number=1, source="ocr_text")],
            "vendor_identifier": [EvidenceReference(page_number=1, source="ocr_text")],
            "currency": [EvidenceReference(page_number=1, source="ocr_text")],
            "total": [EvidenceReference(page_number=1, source="ocr_text")],
            "subtotal": [EvidenceReference(page_number=1, source="ocr_text")],
            "tax": [EvidenceReference(page_number=1, source="ocr_text")],
        },
    )

    metrics = aggregate_extraction_metrics([(extraction, gt)])
    assert metrics.field_count == 9
    assert metrics.exact_match_count == 9
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1 == 1.0
    assert metrics.line_item_f1 == 1.0
    assert metrics.grounded_evidence_rate == 1.0


def test_evaluate_extraction_pair_partial_and_missing() -> None:
    gt = GroundTruthInvoice(
        invoice_number="INV-001",
        invoice_date="2026-03-01",
        due_date="2026-03-31",
        vendor_name="Acme Corp",
        vendor_tax_id=None,
        currency="USD",
        total_amount=Decimal("100.00"),
        subtotal_amount=None,
        tax_amount=None,
        line_items=[],
        expected_finding_types=[],
        expected_verdict="clear",
        ocr_transcript="INV-001 $100.00",
    )

    # Missing invoice_date, wrong invoice_number
    extraction = InvoiceExtraction(
        document_type="invoice",
        invoice_number="INV-999",  # wrong
        invoice_date=None,  # missing
        due_date=None,  # missing
        vendor_name="Acme Corp",  # correct
        currency="USD",  # correct
        total=Decimal("100.00"),  # correct
        line_items=[],
    )

    tp, fp, fn, exact, *_ = evaluate_extraction_pair(extraction, gt)
    # TP: vendor_name, currency, total -> 3
    # FP: invoice_number -> 1
    # FN: invoice_number, invoice_date, due_date -> 3
    assert tp == 3
    assert fp == 1
    assert fn == 3
    assert exact == 3

    metrics = aggregate_extraction_metrics([(extraction, gt)])
    assert metrics.precision == round(3 / 4, 4)
    assert metrics.recall == round(3 / 6, 4)
    assert metrics.grounded_evidence_rate == 0.0  # no evidence provided


def test_aggregate_extraction_metrics_empty() -> None:
    metrics = aggregate_extraction_metrics([])
    assert metrics.field_count == 0
    assert metrics.exact_match_count == 0
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1 == 1.0
    assert metrics.line_item_f1 == 1.0
    assert metrics.grounded_evidence_rate == 1.0
