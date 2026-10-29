"""Typed verification finding contract tests."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from veridoc.verification.models import VerificationFinding, VerificationResult


def test_verification_finding_preserves_structured_statistical_evidence() -> None:
    finding = VerificationFinding(
        finding_type="historical_total_outlier",
        severity="high",
        explanation="The invoice total is outside the established vendor range.",
        comparison_source="vendor_history",
        deterministic_rule="absolute_z_score >= 3",
        observed_value="18400.00",
        expected_range=("5600.00", "8800.00"),
        historical_sample_size=6,
        historical_mean="7200.00",
        historical_standard_deviation="1600.00",
        z_score="7.00",
        details={"currency": "USD"},
    )

    assert finding.historical_mean == Decimal("7200.00")
    assert finding.expected_range == ("5600.00", "8800.00")
    assert VerificationResult(findings=[finding]).findings == [finding]


def test_verification_finding_rejects_invalid_evidence() -> None:
    with pytest.raises(ValidationError):
        VerificationFinding(
            finding_type="unknown",
            severity="high",
            explanation="Invalid finding type.",
            comparison_source="vendor_history",
            deterministic_rule="rule",
        )
    with pytest.raises(ValidationError):
        VerificationFinding(
            finding_type="insufficient_history",
            severity="info",
            explanation="",
            comparison_source="vendor_history",
            deterministic_rule="sample_size < 3",
        )
    with pytest.raises(ValidationError):
        VerificationResult(unexpected="value")


def test_verification_finding_accepts_duplicate_line_item() -> None:
    finding = VerificationFinding(
        finding_type="duplicate_line_item",
        severity="high",
        explanation="Line item 1 is a duplicate of line item 0.",
        comparison_source="invoice_line_items",
        deterministic_rule="line items within an invoice must be unique by product identifier or description",
        observed_value="product:sku-100",
        expected_value="unique line item",
        details={"line_item_index": 1, "duplicate_of_index": 0, "match_type": "exact"},
    )
    assert finding.finding_type == "duplicate_line_item"
    assert finding.severity == "high"


def test_verification_finding_accepts_non_positive_invoice_total() -> None:
    finding = VerificationFinding(
        finding_type="non_positive_invoice_total",
        severity="high",
        explanation="The invoice total is negative (-100.00).",
        comparison_source="invoice_fields",
        deterministic_rule="invoice.total > 0",
        observed_value="-100.00",
        expected_value="> 0.00",
        details={
            "field": "total",
            "total": "-100.00",
            "is_zero": False,
            "is_negative": True,
        },
    )
    assert finding.finding_type == "non_positive_invoice_total"
    assert finding.severity == "high"


def test_verification_finding_accepts_non_positive_line_item() -> None:
    finding = VerificationFinding(
        finding_type="non_positive_line_item",
        severity="high",
        explanation="Line item 0 ('Widget') has a negative total price (-50.00).",
        comparison_source="invoice_line_items",
        deterministic_rule="line_item.quantity > 0 and line_item.unit_price > 0 and line_item.total_price > 0",
        observed_value="total_price=-50.00",
        expected_value="> 0.00",
        details={
            "line_item_index": 0,
            "product_identifier": "SKU-1",
            "description": "Widget",
            "field": "total_price",
            "total_price": "-50.00",
            "is_zero": False,
            "is_negative": True,
        },
    )
    assert finding.finding_type == "non_positive_line_item"
    assert finding.severity == "high"


def test_verification_finding_accepts_non_positive_subtotal() -> None:
    finding = VerificationFinding(
        finding_type="non_positive_subtotal",
        severity="high",
        explanation="The invoice subtotal is negative (-50.00).",
        comparison_source="invoice_fields",
        deterministic_rule="invoice.subtotal > 0",
        observed_value="-50.00",
        expected_value="> 0.00",
        details={
            "field": "subtotal",
            "subtotal": "-50.00",
            "is_zero": False,
            "is_negative": True,
        },
    )
    assert finding.finding_type == "non_positive_subtotal"
    assert finding.severity == "high"


def test_verification_finding_accepts_negative_tax() -> None:
    finding = VerificationFinding(
        finding_type="negative_tax",
        severity="high",
        explanation="The invoice tax amount is negative (-15.00).",
        comparison_source="invoice_fields",
        deterministic_rule="invoice.tax >= 0",
        observed_value="-15.00",
        expected_value=">= 0.00",
        details={
            "field": "tax",
            "tax": "-15.00",
            "is_negative": True,
        },
    )
    assert finding.finding_type == "negative_tax"
    assert finding.severity == "high"


def test_verification_finding_accepts_invalid_discount() -> None:
    finding = VerificationFinding(
        finding_type="invalid_discount",
        severity="high",
        explanation="The invoice discount amount is negative (-10.00).",
        comparison_source="invoice_fields",
        deterministic_rule="invoice.discount >= 0",
        observed_value="-10.00",
        expected_value=">= 0.00",
        details={
            "field": "discount",
            "discount": "-10.00",
            "reason": "negative_discount",
            "is_negative": True,
        },
    )
    assert finding.finding_type == "invalid_discount"
    assert finding.severity == "high"


def test_verification_finding_accepts_rounding_discrepancy() -> None:
    finding = VerificationFinding(
        finding_type="rounding_discrepancy",
        severity="low",
        explanation="The invoice total has a fractional rounding discrepancy of 0.01 within the tolerance of 0.02.",
        comparison_source="invoice_fields",
        deterministic_rule="abs(subtotal + tax - discount - total) <= 0.02",
        observed_value="100.01",
        expected_value="100.00",
        details={
            "currency": "USD",
            "discrepancy": "0.01",
            "tolerance": "0.02",
            "component": "invoice_total",
        },
    )
    assert finding.finding_type == "rounding_discrepancy"
    assert finding.severity == "low"
    assert finding.details["discrepancy"] == "0.01"
    assert finding.details["tolerance"] == "0.02"
    assert finding.details["component"] == "invoice_total"


def test_verification_finding_accepts_payment_terms_due_date_mismatch() -> None:
    finding = VerificationFinding(
        finding_type="payment_terms_due_date_mismatch",
        severity="high",
        explanation="The invoice due date (2026-08-10) is 21 days earlier than the 30-day payment terms specify (expected 2026-08-31).",
        comparison_source="invoice_fields",
        deterministic_rule="invoice.due_date == invoice.invoice_date + payment_terms_days",
        observed_value="2026-08-10",
        expected_value="2026-08-31",
        details={
            "payment_terms": "Net 30",
            "terms_days": 30,
            "expected_due_date": "2026-08-31",
            "observed_due_date": "2026-08-10",
            "discrepancy_days": -21,
            "is_accelerated": True,
        },
    )
    assert finding.finding_type == "payment_terms_due_date_mismatch"
    assert finding.severity == "high"
    assert finding.details["discrepancy_days"] == -21
    assert finding.details["is_accelerated"] is True


def test_verification_finding_accepts_excessive_due_date_window() -> None:
    finding = VerificationFinding(
        finding_type="excessive_due_date_window",
        severity="medium",
        explanation="The invoice due date (2028-01-01) is 518 days after the invoice date (2026-08-01), exceeding the maximum credit window of 365 days.",
        comparison_source="invoice_fields",
        deterministic_rule="due_date - invoice_date <= 365 days",
        observed_value="2028-01-01",
        expected_value="2027-08-01",
        details={
            "credit_window_days": 518,
            "max_allowed_days": 365,
            "invoice_date": "2026-08-01",
            "due_date": "2028-01-01",
        },
    )
    assert finding.finding_type == "excessive_due_date_window"
    assert finding.severity == "medium"
    assert finding.details["credit_window_days"] == 518
    assert finding.details["max_allowed_days"] == 365


def test_verification_finding_accepts_unsupported_document_type() -> None:
    finding = VerificationFinding(
        finding_type="unsupported_document_type",
        severity="high",
        explanation="The extracted document is classified as a purchase order, not an invoice.",
        comparison_source="invoice_fields",
        deterministic_rule="document_type == 'invoice'",
        observed_value="purchase_order",
        expected_value="invoice",
        details={"document_type": "purchase_order"},
    )
    assert finding.finding_type == "unsupported_document_type"
    assert finding.severity == "high"
    assert finding.details["document_type"] == "purchase_order"


def test_verification_finding_accepts_extraction_uncertainty() -> None:
    finding = VerificationFinding(
        finding_type="extraction_uncertainty",
        severity="medium",
        explanation="Extraction uncertainty declared for field 'total': Watermark obscures the last digit of the total.",
        comparison_source="invoice_fields",
        deterministic_rule="len(invoice.uncertainties) == 0",
        observed_value="Watermark obscures the last digit of the total.",
        expected_value=None,
        details={
            "field": "total",
            "reason": "Watermark obscures the last digit of the total.",
            "uncertainty_index": 0,
        },
    )
    assert finding.finding_type == "extraction_uncertainty"
    assert finding.severity == "medium"
    assert finding.details["field"] == "total"
    assert finding.details["uncertainty_index"] == 0


def test_verification_finding_accepts_missing_required_field() -> None:
    finding = VerificationFinding(
        finding_type="missing_required_field",
        severity="high",
        explanation="The required invoice field 'invoice_number' is missing.",
        comparison_source="invoice_fields",
        deterministic_rule="invoice.invoice_number is not None",
        observed_value=None,
        expected_value="invoice_number",
        details={"field": "invoice_number"},
    )
    assert finding.finding_type == "missing_required_field"
    assert finding.severity == "high"
    assert finding.details["field"] == "invoice_number"


def test_verification_finding_accepts_incomplete_line_item() -> None:
    finding = VerificationFinding(
        finding_type="incomplete_line_item",
        severity="medium",
        explanation="The line item has no identifying value.",
        comparison_source="invoice_line_items",
        deterministic_rule="line_item.product_identifier or line_item.description is present",
        observed_value=None,
        expected_value="identity",
        details={"line_item_index": 0, "field": "identity"},
    )
    assert finding.finding_type == "incomplete_line_item"
    assert finding.severity == "medium"
    assert finding.details == {"line_item_index": 0, "field": "identity"}


def test_verification_finding_accepts_invalid_bank_account() -> None:
    finding = VerificationFinding(
        finding_type="invalid_bank_account",
        severity="high",
        explanation="The vendor bank account fails its IBAN checksum.",
        comparison_source="invoice_fields",
        deterministic_rule="IBAN mod-97 remainder == 1",
        observed_value="GB00BARC20201512345678",
        details={
            "field": "vendor_bank_account",
            "account": "GB00BARC20201512345678",
            "reason": "checksum",
        },
    )
    assert finding.finding_type == "invalid_bank_account"
    assert finding.severity == "high"
    assert finding.details["reason"] == "checksum"

def test_verification_finding_accepts_invalid_tax_id() -> None:
    finding = VerificationFinding(
        finding_type="invalid_tax_id",
        severity="medium",
        explanation="The vendor VAT number does not match its country structure.",
        comparison_source="invoice_fields",
        deterministic_rule="vendor_tax_id matches the country VAT structure",
        observed_value="DE12345",
        details={"field": "vendor_tax_id", "tax_id": "DE12345", "country": "DE"},
    )
    assert finding.finding_type == "invalid_tax_id"
    assert finding.severity == "medium"
    assert finding.details["country"] == "DE"
