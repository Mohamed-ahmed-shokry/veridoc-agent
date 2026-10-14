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
    assert finding.deterministic_rule == "abs(subtotal + tax - discount - total) <= 0.02"
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
    assert check_arithmetic(InvoiceExtraction(document_type="invoice", total="100.00")) == []

    # Missing total
    assert check_arithmetic(InvoiceExtraction(document_type="invoice", subtotal="100.00")) == []

    # Both tax and discount missing, subtotal == total
    assert check_arithmetic(InvoiceExtraction(document_type="invoice", subtotal="100.00", total="100.00")) == []

    # Both tax and discount missing, subtotal != total (indeterminate, safely skipped)
    assert check_arithmetic(InvoiceExtraction(document_type="invoice", subtotal="100.00", total="120.00")) == []
