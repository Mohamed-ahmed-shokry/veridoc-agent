"""Deterministic non-positive line-item detection tests.

The non-positive line-item check fires whenever an invoice line item has an
observed quantity, unit price, or total price that is zero or negative (<= 0).
Negative line items (high severity) catch unauthorized credit lines, return
deductions, or OCR minus-sign misinterpretations. Zero line items (medium severity)
catch promotional items, placeholder lines, or price extraction dropouts.
"""

from __future__ import annotations

from decimal import Decimal

from veridoc.extraction.models import InvoiceExtraction, InvoiceLineItem
from veridoc.persistence.protocol import InvoiceRepository
from veridoc.processing.verdict import derive_verdict
from veridoc.verification.line_item_amounts import check_non_positive_line_items
from veridoc.verification.models import VerificationResult
from veridoc.verification.references import HistoricalInvoice, PurchaseOrder
from veridoc.verification.service import VerificationService


def _invoice(**kwargs: object) -> InvoiceExtraction:
    """Build a minimal InvoiceExtraction with overridable keyword arguments."""
    defaults: dict[str, object] = {"document_type": "invoice"}
    defaults.update(kwargs)
    return InvoiceExtraction(**defaults)  # type: ignore[arg-type]


def _line_item(**kwargs: object) -> InvoiceLineItem:
    """Build a minimal InvoiceLineItem with overridable keyword arguments."""
    processed: dict[str, object] = {}
    for k, v in kwargs.items():
        if k in ("quantity", "unit_price", "total_price") and isinstance(v, str):
            processed[k] = Decimal(v)
        else:
            processed[k] = v
    return InvoiceLineItem(**processed)  # type: ignore[arg-type]


class _StubRepository(InvoiceRepository):
    """Minimal repository stub for verification service tests."""

    def list_vendor_invoices(self, vendor_key: str) -> list[HistoricalInvoice]:
        return []

    def get_purchase_order(
        self, vendor_key: str, purchase_order_number: str
    ) -> PurchaseOrder | None:
        return None


# ---------------------------------------------------------------------------
# Cases that should NOT produce a finding
# ---------------------------------------------------------------------------


def test_no_finding_when_line_items_are_empty() -> None:
    invoice = _invoice(line_items=[])
    assert check_non_positive_line_items(invoice) == []


def test_no_finding_when_single_line_item_is_positive() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                description="Consulting",
                quantity="2",
                unit_price="150.00",
                total_price="300.00",
            )
        ]
    )
    assert check_non_positive_line_items(invoice) == []


def test_no_finding_when_multiple_line_items_all_positive() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                product_identifier="SKU-1",
                quantity="10",
                unit_price="25.00",
                total_price="250.00",
            ),
            _line_item(
                product_identifier="SKU-2",
                quantity="1",
                unit_price="500.00",
                total_price="500.00",
            ),
        ]
    )
    assert check_non_positive_line_items(invoice) == []


def test_no_finding_when_all_numerical_fields_are_absent() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                description="Service description only",
                product_identifier="SRV-100",
                quantity=None,
                unit_price=None,
                total_price=None,
            )
        ]
    )
    assert check_non_positive_line_items(invoice) == []


def test_no_finding_when_quantity_is_absent_and_prices_are_positive() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                description="Flat rate service",
                quantity=None,
                unit_price="200.00",
                total_price="200.00",
            )
        ]
    )
    assert check_non_positive_line_items(invoice) == []


def test_no_finding_when_unit_price_is_absent_and_others_positive() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                description="Lump sum delivery",
                quantity="1",
                unit_price=None,
                total_price="1500.00",
            )
        ]
    )
    assert check_non_positive_line_items(invoice) == []


def test_no_finding_when_total_price_is_absent_and_others_positive() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                description="Hourly work",
                quantity="40",
                unit_price="75.00",
                total_price=None,
            )
        ]
    )
    assert check_non_positive_line_items(invoice) == []


def test_no_finding_when_values_are_minimal_positive() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                quantity="0.0001",
                unit_price="0.01",
                total_price="0.000001",
            )
        ]
    )
    assert check_non_positive_line_items(invoice) == []


# ---------------------------------------------------------------------------
# Negative value cases (SHOULD produce high-severity finding)
# ---------------------------------------------------------------------------


def test_finding_produced_when_total_price_is_negative() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                product_identifier="DISC-10",
                description="Promotional rebate",
                quantity="1",
                unit_price="50.00",
                total_price="-50.00",
            )
        ]
    )
    findings = check_non_positive_line_items(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "non_positive_line_item"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_line_items"
    assert (
        finding.deterministic_rule
        == "line_item.quantity > 0 and line_item.unit_price > 0 and line_item.total_price > 0"
    )
    assert finding.observed_value == "total_price=-50.00"
    assert finding.expected_value == "> 0.00"
    assert "DISC-10" in finding.explanation
    assert "negative" in finding.explanation
    assert finding.details["line_item_index"] == 0
    assert finding.details["product_identifier"] == "DISC-10"
    assert finding.details["description"] == "Promotional rebate"
    assert finding.details["field"] == "total_price"
    assert finding.details["total_price"] == "-50.00"
    assert finding.details["is_negative"] is True
    assert finding.details["is_zero"] is False


def test_finding_produced_when_quantity_is_negative() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                description="Returned item",
                quantity="-2",
                unit_price="30.00",
                total_price="-60.00",
            )
        ]
    )
    findings = check_non_positive_line_items(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "non_positive_line_item"
    assert finding.severity == "high"
    assert finding.details["is_negative"] is True
    assert finding.details["is_zero"] is False
    assert "quantity" in str(finding.details["field"])
    assert "total_price" in str(finding.details["field"])


def test_finding_produced_when_unit_price_is_negative() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                description="Negative rate allowance",
                quantity="5",
                unit_price="-20.00",
                total_price="-100.00",
            )
        ]
    )
    findings = check_non_positive_line_items(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "non_positive_line_item"
    assert finding.severity == "high"
    assert finding.details["is_negative"] is True


def test_finding_produced_when_micro_negative() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                total_price="-0.000001",
            )
        ]
    )
    findings = check_non_positive_line_items(invoice)

    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].details["is_negative"] is True


def test_finding_produced_when_large_negative() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                total_price="-999999.99",
            )
        ]
    )
    findings = check_non_positive_line_items(invoice)

    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].details["is_negative"] is True


# ---------------------------------------------------------------------------
# Zero value cases (SHOULD produce medium-severity finding)
# ---------------------------------------------------------------------------


def test_finding_produced_when_total_price_is_zero() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                description="Sample gift",
                quantity="1",
                unit_price="0.00",
                total_price="0.00",
            )
        ]
    )
    findings = check_non_positive_line_items(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "non_positive_line_item"
    assert finding.severity == "medium"
    assert finding.comparison_source == "invoice_line_items"
    assert finding.details["is_negative"] is False
    assert finding.details["is_zero"] is True
    assert "Sample gift" in finding.explanation
    assert "zero" in finding.explanation


def test_finding_produced_when_quantity_is_zero() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                product_identifier="SVC-ZERO",
                quantity="0",
                unit_price="100.00",
                total_price="0.00",
            )
        ]
    )
    findings = check_non_positive_line_items(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "non_positive_line_item"
    assert finding.severity == "medium"
    assert finding.details["is_negative"] is False
    assert finding.details["is_zero"] is True


def test_finding_produced_when_unit_price_is_zero_alone() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                description="Zero unit price promo",
                quantity="5",
                unit_price="0.00",
                total_price="0.00",
            )
        ]
    )
    findings = check_non_positive_line_items(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "non_positive_line_item"
    assert finding.severity == "medium"
    assert finding.details["is_zero"] is True
    assert finding.details["is_negative"] is False


def test_finding_produced_with_decimal_zero_representations() -> None:
    for zero_val in (Decimal(0), Decimal("0.00"), Decimal("0.000000")):
        invoice = _invoice(line_items=[_line_item(total_price=zero_val)])
        findings = check_non_positive_line_items(invoice)
        assert len(findings) == 1
        assert findings[0].severity == "medium"
        assert findings[0].details["is_zero"] is True


# ---------------------------------------------------------------------------
# Compound, mixed, and multi-line item cases
# ---------------------------------------------------------------------------


def test_finding_severity_high_when_mixed_negative_and_zero_fields() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                description="Mixed sign line item",
                quantity="-1",
                unit_price="0.00",
                total_price="0.00",
            )
        ]
    )
    findings = check_non_positive_line_items(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "high"
    assert finding.details["is_negative"] is True
    assert finding.details["is_zero"] is False


def test_finding_label_falls_back_to_description_when_no_product_identifier() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                product_identifier=None,
                description="Consulting Service",
                total_price="-100.00",
            )
        ]
    )
    findings = check_non_positive_line_items(invoice)

    assert len(findings) == 1
    assert "Consulting Service" in findings[0].explanation


def test_finding_label_when_both_description_and_product_id_are_absent() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                product_identifier=None,
                description=None,
                total_price="-100.00",
            )
        ]
    )
    findings = check_non_positive_line_items(invoice)

    assert len(findings) == 1
    assert "Line item 0 has negative" in findings[0].explanation


def test_multiple_line_items_mixed_positive_and_non_positive() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(
                description="Valid Item A",
                quantity="1",
                unit_price="100.00",
                total_price="100.00",
            ),
            _line_item(
                description="Negative Item B",
                quantity="1",
                unit_price="-20.00",
                total_price="-20.00",
            ),
            _line_item(
                description="Valid Item C",
                quantity="2",
                unit_price="50.00",
                total_price="100.00",
            ),
            _line_item(
                description="Zero Item D",
                quantity="0",
                unit_price="0.00",
                total_price="0.00",
            ),
        ]
    )
    findings = check_non_positive_line_items(invoice)

    assert len(findings) == 2
    # First finding is for line item 1 (Negative Item B)
    assert findings[0].details["line_item_index"] == 1
    assert findings[0].severity == "high"
    assert findings[0].details["description"] == "Negative Item B"
    # Second finding is for line item 3 (Zero Item D)
    assert findings[1].details["line_item_index"] == 3
    assert findings[1].severity == "medium"
    assert findings[1].details["description"] == "Zero Item D"


def test_all_line_items_non_positive() -> None:
    invoice = _invoice(
        line_items=[
            _line_item(total_price="-10.00"),
            _line_item(total_price="0.00"),
            _line_item(total_price="-5.00"),
        ]
    )
    findings = check_non_positive_line_items(invoice)

    assert len(findings) == 3
    assert [f.details["line_item_index"] for f in findings] == [0, 1, 2]
    assert [f.severity for f in findings] == ["high", "medium", "high"]


def test_input_invoice_immutability() -> None:
    line_item = _line_item(
        description="Immutable item",
        quantity="2",
        unit_price="50.00",
        total_price="-100.00",
    )
    invoice = _invoice(line_items=[line_item])
    original_dict = invoice.model_dump()

    check_non_positive_line_items(invoice)

    assert invoice.model_dump() == original_dict


# ---------------------------------------------------------------------------
# VerificationService and ProcessingVerdict Integration Tests
# ---------------------------------------------------------------------------


def test_verification_service_includes_negative_line_item_finding() -> None:
    invoice = _invoice(
        vendor_name="Acme Corp",
        invoice_number="INV-001",
        subtotal="80.00",
        tax="0.00",
        discount="0.00",
        total="80.00",
        line_items=[
            _line_item(
                description="Main product",
                quantity="1",
                unit_price="100.00",
                total_price="100.00",
            ),
            _line_item(
                description="Credit adjustment",
                quantity="1",
                unit_price="-20.00",
                total_price="-20.00",
            ),
        ],
    )
    service = VerificationService(repository=_StubRepository())
    result = service.verify(invoice)

    finding_types = [f.finding_type for f in result.findings]
    assert "non_positive_line_item" in finding_types
    non_pos_findings = [
        f for f in result.findings if f.finding_type == "non_positive_line_item"
    ]
    assert len(non_pos_findings) == 1
    assert non_pos_findings[0].severity == "high"


def test_verification_service_includes_zero_line_item_finding() -> None:
    invoice = _invoice(
        vendor_name="Acme Corp",
        invoice_number="INV-002",
        subtotal="100.00",
        tax="0.00",
        discount="0.00",
        total="100.00",
        line_items=[
            _line_item(
                description="Main product",
                quantity="1",
                unit_price="100.00",
                total_price="100.00",
            ),
            _line_item(
                description="Free sample",
                quantity="1",
                unit_price="0.00",
                total_price="0.00",
            ),
        ],
    )
    service = VerificationService(repository=_StubRepository())
    result = service.verify(invoice)

    finding_types = [f.finding_type for f in result.findings]
    assert "non_positive_line_item" in finding_types
    non_pos_findings = [
        f for f in result.findings if f.finding_type == "non_positive_line_item"
    ]
    assert len(non_pos_findings) == 1
    assert non_pos_findings[0].severity == "medium"


def test_verdict_derivation_drives_review_required_for_negative_line_item() -> None:
    finding = check_non_positive_line_items(
        _invoice(
            line_items=[
                _line_item(
                    description="Rebate",
                    total_price="-50.00",
                )
            ]
        )
    )
    assert len(finding) == 1
    verdict = derive_verdict(VerificationResult(findings=finding))

    assert verdict.status == "review_required"
    assert verdict.highest_severity == "high"
    assert verdict.finding_count == 1
    assert "1 deterministic verification finding requires review" in verdict.summary


def test_verdict_derivation_drives_review_required_for_zero_line_item() -> None:
    finding = check_non_positive_line_items(
        _invoice(
            line_items=[
                _line_item(
                    description="Zero sample",
                    total_price="0.00",
                )
            ]
        )
    )
    assert len(finding) == 1
    verdict = derive_verdict(VerificationResult(findings=finding))

    assert verdict.status == "review_required"
    assert verdict.highest_severity == "medium"
    assert verdict.finding_count == 1
