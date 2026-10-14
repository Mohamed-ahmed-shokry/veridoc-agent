"""Deterministic invoice arithmetic verification tests."""

from veridoc.extraction.models import InvoiceExtraction, InvoiceLineItem
from veridoc.verification.arithmetic import check_arithmetic


def test_arithmetic_checks_accept_a_consistent_invoice() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        subtotal="200.00",
        tax="40.00",
        discount="10.00",
        total="230.00",
        invoice_date="2026-08-01",
        due_date="2026-08-31",
        line_items=[
            InvoiceLineItem(quantity="2", unit_price="100.00", total_price="200.00")
        ],
    )

    assert check_arithmetic(invoice) == []


def test_arithmetic_checks_report_each_inconsistent_fact() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        subtotal="180.00",
        tax="40.00",
        discount="10.00",
        total="250.00",
        invoice_date="2026-09-01",
        due_date="2026-08-31",
        line_items=[
            InvoiceLineItem(
                product_identifier="CONSULTING",
                quantity="2",
                unit_price="100.00",
                total_price="150.00",
            )
        ],
    )

    findings = check_arithmetic(invoice)

    assert [finding.finding_type for finding in findings] == [
        "invoice_total_mismatch",
        "line_item_amount_mismatch",
        "line_items_subtotal_mismatch",
        "invoice_date_after_due_date",
    ]
    assert findings[1].details["line_item_index"] == 0
    assert findings[2].expected_value == "150.00"


def test_arithmetic_handles_the_largest_supported_operands() -> None:
    maximum = "999999999999999999.999999"
    invoice = InvoiceExtraction(
        document_type="invoice",
        line_items=[
            InvoiceLineItem(
                quantity=maximum,
                unit_price=maximum,
                total_price="0",
            )
        ],
    )

    findings = check_arithmetic(invoice)

    assert [finding.finding_type for finding in findings] == [
        "line_item_amount_mismatch"
    ]


def test_invoice_total_rounding_discrepancy_within_default_tolerance() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        currency="USD",
        subtotal="100.00",
        tax="10.00",
        discount="0.00",
        total="110.01",
    )
    findings = check_arithmetic(invoice)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "rounding_discrepancy"
    assert finding.severity == "low"
    assert finding.comparison_source == "invoice_fields"
    assert (
        finding.deterministic_rule == "abs(subtotal + tax - discount - total) <= 0.02"
    )
    assert finding.observed_value == "110.01"
    assert finding.expected_value == "110.00"
    assert finding.details == {
        "currency": "USD",
        "discrepancy": "0.01",
        "tolerance": "0.02",
        "component": "invoice_total",
    }


def test_invoice_total_rounding_discrepancy_at_exact_tolerance_boundary() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        currency="EUR",
        subtotal="100.00",
        tax="10.00",
        discount="0.00",
        total="110.02",
    )
    findings = check_arithmetic(invoice)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "rounding_discrepancy"
    assert finding.severity == "low"
    assert finding.details["discrepancy"] == "0.02"


def test_invoice_total_material_mismatch_exceeding_tolerance() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        currency="USD",
        subtotal="100.00",
        tax="10.00",
        discount="0.00",
        total="110.03",
    )
    findings = check_arithmetic(invoice)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "invoice_total_mismatch"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "subtotal + tax - discount == total"
    assert finding.observed_value == "110.03"
    assert finding.expected_value == "110.00"
    assert finding.details == {
        "currency": "USD",
        "discrepancy": "0.03",
        "tolerance": "0.02",
    }


def test_invoice_total_omitted_discount_defaults_to_zero_with_tax() -> None:
    # Consistent invoice with omitted discount
    consistent = InvoiceExtraction(
        document_type="invoice",
        subtotal="100.00",
        tax="20.00",
        discount=None,
        total="120.00",
    )
    assert check_arithmetic(consistent) == []

    # Rounding difference with omitted discount
    rounding = InvoiceExtraction(
        document_type="invoice",
        currency="USD",
        subtotal="100.00",
        tax="20.00",
        discount=None,
        total="120.01",
    )
    rounding_findings = check_arithmetic(rounding)
    assert len(rounding_findings) == 1
    assert rounding_findings[0].finding_type == "rounding_discrepancy"

    # Material mismatch with omitted discount
    mismatch = InvoiceExtraction(
        document_type="invoice",
        currency="USD",
        subtotal="100.00",
        tax="20.00",
        discount=None,
        total="150.00",
    )
    mismatch_findings = check_arithmetic(mismatch)
    assert len(mismatch_findings) == 1
    assert mismatch_findings[0].finding_type == "invoice_total_mismatch"


def test_invoice_total_omitted_tax_defaults_to_zero_with_discount() -> None:
    # Consistent invoice with omitted tax (zero-rated / tax exempt)
    consistent = InvoiceExtraction(
        document_type="invoice",
        subtotal="100.00",
        tax=None,
        discount="10.00",
        total="90.00",
    )
    assert check_arithmetic(consistent) == []

    # Rounding difference with omitted tax
    rounding = InvoiceExtraction(
        document_type="invoice",
        currency="USD",
        subtotal="100.00",
        tax=None,
        discount="10.00",
        total="90.01",
    )
    findings = check_arithmetic(rounding)
    assert len(findings) == 1
    assert findings[0].finding_type == "rounding_discrepancy"

    # Material mismatch with omitted tax
    mismatch = InvoiceExtraction(
        document_type="invoice",
        currency="USD",
        subtotal="100.00",
        tax=None,
        discount="10.00",
        total="80.00",
    )
    findings = check_arithmetic(mismatch)
    assert len(findings) == 1
    assert findings[0].finding_type == "invoice_total_mismatch"


def test_invoice_total_custom_tolerance_parameter() -> None:
    from decimal import Decimal

    invoice = InvoiceExtraction(
        document_type="invoice",
        subtotal="100.00",
        tax="10.00",
        discount="0.00",
        total="110.01",
    )

    # Zero tolerance: 0.01 is a material mismatch
    strict_findings = check_arithmetic(invoice, rounding_tolerance=Decimal("0.00"))
    assert len(strict_findings) == 1
    assert strict_findings[0].finding_type == "invoice_total_mismatch"
    assert strict_findings[0].severity == "high"

    # Permissive tolerance: 0.04 is a rounding discrepancy
    invoice_04 = InvoiceExtraction(
        document_type="invoice",
        subtotal="100.00",
        tax="10.00",
        discount="0.00",
        total="110.04",
    )
    lenient_findings = check_arithmetic(invoice_04, rounding_tolerance=Decimal("0.05"))
    assert len(lenient_findings) == 1
    assert lenient_findings[0].finding_type == "rounding_discrepancy"
    assert lenient_findings[0].severity == "low"


def test_invoice_total_missing_fields_safely_ignored() -> None:
    # Missing subtotal
    assert (
        check_arithmetic(InvoiceExtraction(document_type="invoice", total="100.00"))
        == []
    )

    # Missing total
    assert (
        check_arithmetic(InvoiceExtraction(document_type="invoice", subtotal="100.00"))
        == []
    )

    # Both tax and discount missing, subtotal == total
    assert (
        check_arithmetic(
            InvoiceExtraction(
                document_type="invoice", subtotal="100.00", total="100.00"
            )
        )
        == []
    )

    # Both tax and discount missing, subtotal != total (indeterminate, safely skipped)
    assert (
        check_arithmetic(
            InvoiceExtraction(
                document_type="invoice", subtotal="100.00", total="120.00"
            )
        )
        == []
    )


def test_line_item_amount_rounding_discrepancy_within_tolerance() -> None:
    # 3 x 33.33 = 99.99, but line item total is 100.00 (0.01 discrepancy)
    invoice = InvoiceExtraction(
        document_type="invoice",
        line_items=[
            InvoiceLineItem(
                product_identifier="SKU-1",
                quantity="3",
                unit_price="33.33",
                total_price="100.00",
            )
        ],
    )
    findings = check_arithmetic(invoice)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "rounding_discrepancy"
    assert finding.severity == "low"
    assert finding.comparison_source == "invoice_line_items"
    assert (
        finding.deterministic_rule == "abs(quantity * unit_price - total_price) <= 0.02"
    )
    assert finding.observed_value == "100.00"
    assert finding.expected_value == "99.99"
    assert finding.details == {
        "line_item_index": 0,
        "product_identifier": "SKU-1",
        "discrepancy": "0.01",
        "tolerance": "0.02",
        "component": "line_item_amount",
    }


def test_line_item_amount_rounding_discrepancy_at_exact_boundary() -> None:
    # 2 x 50.00 = 100.00, total_price is 100.02 (0.02 discrepancy)
    invoice = InvoiceExtraction(
        document_type="invoice",
        line_items=[
            InvoiceLineItem(
                product_identifier="SKU-2",
                quantity="2",
                unit_price="50.00",
                total_price="100.02",
            )
        ],
    )
    findings = check_arithmetic(invoice)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "rounding_discrepancy"
    assert finding.severity == "low"
    assert finding.details["discrepancy"] == "0.02"


def test_line_item_amount_material_mismatch_exceeding_tolerance() -> None:
    # 2 x 50.00 = 100.00, total_price is 100.05 (0.05 discrepancy > 0.02)
    invoice = InvoiceExtraction(
        document_type="invoice",
        line_items=[
            InvoiceLineItem(
                product_identifier="SKU-3",
                quantity="2",
                unit_price="50.00",
                total_price="100.05",
            )
        ],
    )
    findings = check_arithmetic(invoice)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "line_item_amount_mismatch"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_line_items"
    assert finding.deterministic_rule == "quantity * unit_price == total_price"
    assert finding.observed_value == "100.05"
    assert finding.expected_value == "100.00"
    assert finding.details == {
        "line_item_index": 0,
        "product_identifier": "SKU-3",
        "discrepancy": "0.05",
        "tolerance": "0.02",
    }


def test_line_item_amount_missing_fields_skipped() -> None:
    # Missing unit_price
    invoice_no_unit_price = InvoiceExtraction(
        document_type="invoice",
        line_items=[InvoiceLineItem(quantity="2", total_price="100.00")],
    )
    assert check_arithmetic(invoice_no_unit_price) == []

    # Missing quantity
    invoice_no_quantity = InvoiceExtraction(
        document_type="invoice",
        line_items=[InvoiceLineItem(unit_price="50.00", total_price="100.00")],
    )
    assert check_arithmetic(invoice_no_quantity) == []

    # Missing total_price
    invoice_no_total = InvoiceExtraction(
        document_type="invoice",
        line_items=[InvoiceLineItem(quantity="2", unit_price="50.00")],
    )
    assert check_arithmetic(invoice_no_total) == []


def test_line_items_subtotal_rounding_discrepancy_within_tolerance() -> None:
    # Two line items totaling 33.33 + 66.66 = 99.99, subtotal is 100.00 (0.01 discrepancy)
    invoice = InvoiceExtraction(
        document_type="invoice",
        subtotal="100.00",
        line_items=[
            InvoiceLineItem(quantity="1", unit_price="33.33", total_price="33.33"),
            InvoiceLineItem(quantity="1", unit_price="66.66", total_price="66.66"),
        ],
    )
    findings = check_arithmetic(invoice)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "rounding_discrepancy"
    assert finding.severity == "low"
    assert finding.comparison_source == "invoice_line_items"
    assert (
        finding.deterministic_rule
        == "abs(sum(line_item.total_price) - subtotal) <= 0.02"
    )
    assert finding.observed_value == "100.00"
    assert finding.expected_value == "99.99"
    assert finding.details == {
        "line_item_count": 2,
        "discrepancy": "0.01",
        "tolerance": "0.02",
        "component": "line_items_subtotal",
    }


def test_line_items_subtotal_rounding_discrepancy_at_exact_boundary() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        subtotal="100.00",
        line_items=[
            InvoiceLineItem(quantity="1", unit_price="99.98", total_price="99.98"),
        ],
    )
    findings = check_arithmetic(invoice)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "rounding_discrepancy"
    assert finding.severity == "low"
    assert finding.details["discrepancy"] == "0.02"


def test_line_items_subtotal_material_mismatch_exceeding_tolerance() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        subtotal="100.00",
        line_items=[
            InvoiceLineItem(quantity="1", unit_price="90.00", total_price="90.00"),
        ],
    )
    findings = check_arithmetic(invoice)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "line_items_subtotal_mismatch"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_line_items"
    assert finding.deterministic_rule == "sum(line_item.total_price) == subtotal"
    assert finding.observed_value == "100.00"
    assert finding.expected_value == "90.00"
    assert finding.details == {
        "line_item_count": 1,
        "discrepancy": "10.00",
        "tolerance": "0.02",
    }


def test_line_items_subtotal_missing_fields_skipped() -> None:
    # Missing subtotal
    invoice_no_subtotal = InvoiceExtraction(
        document_type="invoice",
        line_items=[InvoiceLineItem(total_price="100.00")],
    )
    assert check_arithmetic(invoice_no_subtotal) == []

    # Empty line items
    invoice_no_items = InvoiceExtraction(
        document_type="invoice",
        subtotal="100.00",
        line_items=[],
    )
    assert check_arithmetic(invoice_no_items) == []

    # One line item missing total_price
    invoice_missing_item_total = InvoiceExtraction(
        document_type="invoice",
        subtotal="100.00",
        line_items=[
            InvoiceLineItem(total_price="50.00"),
            InvoiceLineItem(quantity="1", unit_price="50.00"),  # total_price is None
        ],
    )
    assert check_arithmetic(invoice_missing_item_total) == []


def test_arithmetic_combines_multiple_rounding_discrepancies() -> None:
    # Header total: 100.00 + 10.00 - 0.00 = 110.00 vs 110.01 (0.01 rounding)
    # Line item: 3 x 33.33 = 99.99 vs 100.00 (0.01 rounding)
    # Line items subtotal: sum(100.00) = 100.00 vs subtotal 100.01 (0.01 rounding)
    invoice = InvoiceExtraction(
        document_type="invoice",
        currency="USD",
        subtotal="100.01",
        tax="10.00",
        discount="0.00",
        total="110.02",
        line_items=[
            InvoiceLineItem(
                product_identifier="ITEM-1",
                quantity="3",
                unit_price="33.33",
                total_price="100.00",
            )
        ],
    )
    findings = check_arithmetic(invoice)
    finding_types = [f.finding_type for f in findings]
    assert finding_types == [
        "rounding_discrepancy",
        "rounding_discrepancy",
        "rounding_discrepancy",
    ]
    assert all(f.severity == "low" for f in findings)
    components = [f.details["component"] for f in findings]
    assert components == ["invoice_total", "line_item_amount", "line_items_subtotal"]


def test_arithmetic_does_not_mutate_invoice_extraction() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        currency="USD",
        subtotal="100.00",
        tax="10.00",
        discount=None,
        total="110.01",
        line_items=[
            InvoiceLineItem(
                product_identifier="ITEM-1",
                quantity="3",
                unit_price="33.33",
                total_price="100.00",
            )
        ],
    )
    snapshot = invoice.model_dump()
    _ = check_arithmetic(invoice)
    assert invoice.model_dump() == snapshot


def test_rounding_discrepancy_verdict_derivation() -> None:
    from veridoc.processing.verdict import derive_verdict
    from veridoc.verification.models import VerificationResult

    invoice = InvoiceExtraction(
        document_type="invoice",
        currency="USD",
        subtotal="100.00",
        tax="10.00",
        discount="0.00",
        total="110.01",
    )
    findings = check_arithmetic(invoice)
    verdict = derive_verdict(VerificationResult(findings=findings))
    assert verdict.status == "review_required"
    assert verdict.highest_severity == "low"
    assert verdict.finding_count == 1
    assert "1 deterministic verification finding requires review." in verdict.summary


def test_verification_service_integrates_arithmetic_rounding() -> None:
    from veridoc.verification.service import VerificationService

    class EmptyRepository:
        def list_vendor_invoices(self, vendor_key: str) -> list[object]:
            return []

        def get_purchase_order(self, vendor_key: str, po_number: str) -> None:
            return None

    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Acme Supplies",
        invoice_number="INV-101",
        currency="USD",
        subtotal="100.00",
        tax="10.00",
        discount="0.00",
        total="110.01",
    )
    service = VerificationService(EmptyRepository())  # type: ignore[arg-type]
    result = service.verify(invoice)
    finding_types = [f.finding_type for f in result.findings]
    assert "rounding_discrepancy" in finding_types
