"""Deterministic duplicate line-item detection tests.

The duplicate line-item check detects repeated product identifiers or descriptions
within a single invoice. It differentiates between exact duplicates (same description/product,
quantity, and unit price), which represent high-confidence double billing or OCR
repetition errors (severity: high), and partial duplicates (differing quantity or unit price),
which represent split billing or potential clerical duplication (severity: medium).
"""

from __future__ import annotations

from decimal import Decimal

from veridoc.extraction.models import InvoiceExtraction, InvoiceLineItem
from veridoc.processing.verdict import derive_verdict
from veridoc.verification.duplicate_line_items import check_duplicate_line_items
from veridoc.verification.models import VerificationResult
from veridoc.verification.references import HistoricalInvoice
from veridoc.verification.service import VerificationService


def _invoice(**kwargs: object) -> InvoiceExtraction:
    defaults: dict[str, object] = {"document_type": "invoice"}
    defaults.update(kwargs)
    return InvoiceExtraction(**defaults)  # type: ignore[arg-type]


def _line_item(
    *,
    description: str | None = None,
    product_identifier: str | None = None,
    quantity: str | None = None,
    unit_price: str | None = None,
    total_price: str | None = None,
) -> InvoiceLineItem:
    return InvoiceLineItem(
        description=description,
        product_identifier=product_identifier,
        quantity=Decimal(quantity) if quantity is not None else None,
        unit_price=Decimal(unit_price) if unit_price is not None else None,
        total_price=Decimal(total_price) if total_price is not None else None,
    )


class DummyRepository:
    def list_vendor_invoices(self, vendor_key: str) -> list[HistoricalInvoice]:
        return []

    def get_purchase_order(self, vendor_key: str, po_number: str) -> None:
        return None


# ---------------------------------------------------------------------------
# Cases that should NOT produce a finding
# ---------------------------------------------------------------------------


def test_no_finding_when_line_items_are_empty() -> None:
    invoice = _invoice(line_items=[])
    assert check_duplicate_line_items(invoice) == []


def test_no_finding_when_single_line_item() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                product_identifier="SKU-1",
                description="Widget A",
                quantity="2",
                unit_price="10.00",
                total_price="20.00",
            )
        ]
    )
    assert check_duplicate_line_items(invoice) == []


def test_no_finding_when_all_line_items_are_distinct() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                product_identifier="SKU-1",
                description="Widget A",
                quantity="2",
                unit_price="10.00",
                total_price="20.00",
            ),
            _line_item(
                product_identifier="SKU-2",
                description="Widget B",
                quantity="1",
                unit_price="30.00",
                total_price="30.00",
            ),
            _line_item(
                description="Consulting services",
                quantity="5",
                unit_price="100.00",
                total_price="500.00",
            ),
        ]
    )
    assert check_duplicate_line_items(invoice) == []


def test_no_finding_when_line_items_have_no_identifying_information() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(quantity="1", unit_price="50.00", total_price="50.00"),
            _line_item(quantity="2", unit_price="50.00", total_price="100.00"),
        ]
    )
    assert check_duplicate_line_items(invoice) == []


def test_no_finding_when_descriptions_are_blank_spaces() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(description="   ", quantity="1", unit_price="10.00"),
            _line_item(description="  ", quantity="1", unit_price="10.00"),
        ]
    )
    assert check_duplicate_line_items(invoice) == []


# ---------------------------------------------------------------------------
# Exact duplicate cases (Severity: HIGH)
# ---------------------------------------------------------------------------


def test_exact_duplicate_with_product_identifier() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                product_identifier="SKU-100",
                description="Filter unit",
                quantity="2",
                unit_price="25.00",
                total_price="50.00",
            ),
            _line_item(
                product_identifier="SKU-100",
                description="Filter unit",
                quantity="2",
                unit_price="25.00",
                total_price="50.00",
            ),
        ]
    )
    findings = check_duplicate_line_items(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "duplicate_line_item"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_line_items"
    assert finding.deterministic_rule == (
        "line items within an invoice must be unique by product identifier or description"
    )
    assert finding.observed_value == "product:sku-100"
    assert finding.expected_value == "unique line item"
    assert finding.details == {
        "line_item_index": 1,
        "duplicate_of_index": 0,
        "match_type": "exact",
        "key": "product:sku-100",
        "product_identifier": "SKU-100",
        "description": "Filter unit",
        "quantity": "2",
        "unit_price": "25.00",
    }


def test_exact_duplicate_with_description_only() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                description="Monthly Maintenance Retainer",
                quantity="1",
                unit_price="1500.00",
                total_price="1500.00",
            ),
            _line_item(
                description="Monthly Maintenance Retainer",
                quantity="1",
                unit_price="1500.00",
                total_price="1500.00",
            ),
        ]
    )
    findings = check_duplicate_line_items(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "duplicate_line_item"
    assert finding.severity == "high"
    assert finding.observed_value == "description:monthly maintenance retainer"
    assert finding.details["match_type"] == "exact"
    assert finding.details["line_item_index"] == 1
    assert finding.details["duplicate_of_index"] == 0


def test_normalization_catches_casing_and_whitespace_variants() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                description="Software Support License",
                quantity="1",
                unit_price="500.00",
            ),
            _line_item(
                description="  software   SUPPORT   license  ",
                quantity="1",
                unit_price="500.00",
            ),
        ]
    )
    findings = check_duplicate_line_items(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "high"
    assert finding.observed_value == "description:software support license"
    assert finding.details["match_type"] == "exact"


def test_product_identifier_normalization_catches_variants() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                product_identifier="PART-9901",
                quantity="10",
                unit_price="5.50",
            ),
            _line_item(
                product_identifier="  part-9901  ",
                quantity="10",
                unit_price="5.50",
            ),
        ]
    )
    findings = check_duplicate_line_items(invoice)

    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].observed_value == "product:part-9901"


# ---------------------------------------------------------------------------
# Partial duplicate cases (Severity: MEDIUM)
# ---------------------------------------------------------------------------


def test_partial_duplicate_with_differing_quantity() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                product_identifier="SKU-200",
                quantity="5",
                unit_price="40.00",
            ),
            _line_item(
                product_identifier="SKU-200",
                quantity="10",
                unit_price="40.00",
            ),
        ]
    )
    findings = check_duplicate_line_items(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "duplicate_line_item"
    assert finding.severity == "medium"
    assert finding.details["match_type"] == "partial"
    assert finding.details["quantity"] == "10"
    assert "differing quantity or unit price" in finding.explanation


def test_partial_duplicate_with_differing_unit_price() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                description="Hourly Consulting",
                quantity="8",
                unit_price="150.00",
            ),
            _line_item(
                description="Hourly Consulting",
                quantity="8",
                unit_price="200.00",
            ),
        ]
    )
    findings = check_duplicate_line_items(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "duplicate_line_item"
    assert finding.severity == "medium"
    assert finding.details["match_type"] == "partial"
    assert finding.details["unit_price"] == "200.00"


def test_partial_duplicate_with_missing_quantity() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                product_identifier="SKU-300",
                quantity="1",
                unit_price="100.00",
            ),
            _line_item(
                product_identifier="SKU-300",
                quantity=None,
                unit_price="100.00",
            ),
        ]
    )
    findings = check_duplicate_line_items(invoice)

    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert findings[0].details["match_type"] == "partial"
    assert findings[0].details["quantity"] is None


def test_partial_duplicate_with_missing_unit_price() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                product_identifier="SKU-400",
                quantity="2",
                unit_price="50.00",
            ),
            _line_item(
                product_identifier="SKU-400",
                quantity="2",
                unit_price=None,
            ),
        ]
    )
    findings = check_duplicate_line_items(invoice)

    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert findings[0].details["match_type"] == "partial"
    assert findings[0].details["unit_price"] is None


# ---------------------------------------------------------------------------
# Multiple occurrences and groupings
# ---------------------------------------------------------------------------


def test_triple_duplicate_of_same_line_item() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(product_identifier="SKU-500", quantity="1", unit_price="10.00"),
            _line_item(product_identifier="SKU-500", quantity="1", unit_price="10.00"),
            _line_item(product_identifier="SKU-500", quantity="1", unit_price="10.00"),
        ]
    )
    findings = check_duplicate_line_items(invoice)

    assert len(findings) == 2
    assert findings[0].details["line_item_index"] == 1
    assert findings[0].details["duplicate_of_index"] == 0
    assert findings[1].details["line_item_index"] == 2
    assert findings[1].details["duplicate_of_index"] == 0


def test_multiple_distinct_duplicate_groups() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(product_identifier="SKU-A", quantity="1", unit_price="10.00"),
            _line_item(product_identifier="SKU-B", quantity="2", unit_price="20.00"),
            _line_item(product_identifier="SKU-A", quantity="1", unit_price="10.00"),
            _line_item(product_identifier="SKU-B", quantity="3", unit_price="20.00"),
        ]
    )
    findings = check_duplicate_line_items(invoice)

    assert len(findings) == 2
    finding_a = findings[0]
    assert finding_a.observed_value == "product:sku-a"
    assert finding_a.severity == "high"
    assert finding_a.details["line_item_index"] == 2
    assert finding_a.details["duplicate_of_index"] == 0

    finding_b = findings[1]
    assert finding_b.observed_value == "product:sku-b"
    assert finding_b.severity == "medium"  # quantity differs (2 vs 3)
    assert finding_b.details["line_item_index"] == 3
    assert finding_b.details["duplicate_of_index"] == 1


def test_interleaved_unique_and_duplicate_line_items() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(product_identifier="UNIQUE-1", quantity="1", unit_price="10.00"),
            _line_item(product_identifier="REPEAT-1", quantity="2", unit_price="20.00"),
            _line_item(product_identifier="UNIQUE-2", quantity="3", unit_price="30.00"),
            _line_item(product_identifier="REPEAT-1", quantity="2", unit_price="20.00"),
        ]
    )
    findings = check_duplicate_line_items(invoice)

    assert len(findings) == 1
    assert findings[0].details["line_item_index"] == 3
    assert findings[0].details["duplicate_of_index"] == 1


def test_product_identifier_takes_precedence_over_differing_description() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                product_identifier="SKU-SHARED",
                description="Red widget",
                quantity="1",
                unit_price="15.00",
            ),
            _line_item(
                product_identifier="SKU-SHARED",
                description="Blue widget",
                quantity="1",
                unit_price="15.00",
            ),
        ]
    )
    findings = check_duplicate_line_items(invoice)

    assert len(findings) == 1
    assert findings[0].observed_value == "product:sku-shared"
    assert findings[0].severity == "high"


def test_duplicate_line_item_immutability() -> None:
    line_0 = _line_item(
        product_identifier="IMMUTABLE-1", quantity="1", unit_price="5.00"
    )
    line_1 = _line_item(
        product_identifier="IMMUTABLE-1", quantity="1", unit_price="5.00"
    )
    invoice = _invoice(line_items=[line_0, line_1])

    original_dump = invoice.model_dump()
    check_duplicate_line_items(invoice)
    assert invoice.model_dump() == original_dump


# ---------------------------------------------------------------------------
# Service & Verdict integration
# ---------------------------------------------------------------------------


def test_verification_service_includes_duplicate_line_item_findings() -> None:
    invoice = _invoice(
        vendor_name="Fictional Supplies",
        invoice_number="INV-999",
        currency="USD",
        subtotal="40.00",
        tax="0.00",
        discount="0.00",
        total="40.00",
        line_items=[
            _line_item(
                product_identifier="SKU-DUP",
                quantity="2",
                unit_price="10.00",
                total_price="20.00",
            ),
            _line_item(
                product_identifier="SKU-DUP",
                quantity="2",
                unit_price="10.00",
                total_price="20.00",
            ),
        ],
    )
    result = VerificationService(DummyRepository()).verify(invoice)

    finding_types = [f.finding_type for f in result.findings]
    assert "duplicate_line_item" in finding_types


def test_derive_verdict_high_severity_for_exact_duplicate() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                product_identifier="SKU-EXACT", quantity="1", unit_price="50.00"
            ),
            _line_item(
                product_identifier="SKU-EXACT", quantity="1", unit_price="50.00"
            ),
        ]
    )
    findings = check_duplicate_line_items(invoice)
    verdict = derive_verdict(VerificationResult(findings=findings))

    assert verdict.status == "review_required"
    assert verdict.highest_severity == "high"
    assert verdict.finding_count == 1


def test_derive_verdict_medium_severity_for_partial_duplicate() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                product_identifier="SKU-PARTIAL", quantity="1", unit_price="50.00"
            ),
            _line_item(
                product_identifier="SKU-PARTIAL", quantity="2", unit_price="50.00"
            ),
        ]
    )
    findings = check_duplicate_line_items(invoice)
    verdict = derive_verdict(VerificationResult(findings=findings))

    assert verdict.status == "review_required"
    assert verdict.highest_severity == "medium"
    assert verdict.finding_count == 1
