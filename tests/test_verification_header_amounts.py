"""Deterministic invoice header monetary bound tests.

Covers ``check_non_positive_subtotal``, ``check_negative_tax``,
``check_invalid_discount``, and ``check_header_amounts`` in
``veridoc.verification.header_amounts``, plus ``VerificationService``,
``ExplanationService``, and ``derive_verdict`` integration.
"""

from __future__ import annotations

from decimal import Decimal

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.header_amounts import (
    check_invalid_discount,
    check_negative_tax,
    check_non_positive_subtotal,
)


def _invoice(**kwargs: object) -> InvoiceExtraction:
    """Build a minimal InvoiceExtraction with overridable keyword arguments."""
    defaults: dict[str, object] = {"document_type": "invoice"}
    defaults.update(kwargs)
    return InvoiceExtraction(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# check_non_positive_subtotal: non-triggering paths
# ---------------------------------------------------------------------------


def test_subtotal_no_finding_when_absent() -> None:
    invoice = _invoice(subtotal=None)
    assert check_non_positive_subtotal(invoice) == []


def test_subtotal_no_finding_when_positive() -> None:
    invoice = _invoice(subtotal="100.00")
    assert check_non_positive_subtotal(invoice) == []


def test_subtotal_no_finding_when_minimal_positive() -> None:
    invoice = _invoice(subtotal="0.01")
    assert check_non_positive_subtotal(invoice) == []


def test_subtotal_no_finding_when_micro_positive() -> None:
    invoice = _invoice(subtotal="0.000001")
    assert check_non_positive_subtotal(invoice) == []


def test_subtotal_no_finding_when_large_positive() -> None:
    invoice = _invoice(subtotal="999999999.99")
    assert check_non_positive_subtotal(invoice) == []


# ---------------------------------------------------------------------------
# check_non_positive_subtotal: zero subtotal (medium severity)
# ---------------------------------------------------------------------------


def test_subtotal_finding_when_zero() -> None:
    invoice = _invoice(subtotal="0.00")
    findings = check_non_positive_subtotal(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "non_positive_subtotal"
    assert finding.severity == "medium"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "invoice.subtotal > 0"
    assert finding.observed_value == "0.00"
    assert finding.expected_value == "> 0.00"
    assert "zero" in finding.explanation.lower()
    assert finding.details == {
        "field": "subtotal",
        "subtotal": "0.00",
        "is_zero": True,
        "is_negative": False,
    }


def test_subtotal_finding_when_zero_across_representations() -> None:
    for raw in ("0", "0.000000", Decimal(0), Decimal("-0.00")):
        invoice = _invoice(subtotal=raw)
        findings = check_non_positive_subtotal(invoice)
        assert len(findings) == 1
        assert findings[0].finding_type == "non_positive_subtotal"
        assert findings[0].severity == "medium"
        assert findings[0].details["is_zero"] is True
        assert findings[0].details["is_negative"] is False


def test_subtotal_zero_includes_currency_when_present() -> None:
    invoice = _invoice(subtotal="0.00", currency="USD")
    findings = check_non_positive_subtotal(invoice)

    assert len(findings) == 1
    assert findings[0].details["currency"] == "USD"


# ---------------------------------------------------------------------------
# check_non_positive_subtotal: negative subtotal (high severity)
# ---------------------------------------------------------------------------


def test_subtotal_finding_when_negative() -> None:
    invoice = _invoice(subtotal="-150.00")
    findings = check_non_positive_subtotal(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "non_positive_subtotal"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "invoice.subtotal > 0"
    assert finding.observed_value == "-150.00"
    assert finding.expected_value == "> 0.00"
    assert "negative" in finding.explanation.lower()
    assert finding.details == {
        "field": "subtotal",
        "subtotal": "-150.00",
        "is_zero": False,
        "is_negative": True,
    }


def test_subtotal_finding_when_minimal_and_micro_negative() -> None:
    for raw in ("-0.01", "-0.000001", "-999999.99"):
        invoice = _invoice(subtotal=raw)
        findings = check_non_positive_subtotal(invoice)
        assert len(findings) == 1
        assert findings[0].severity == "high"
        assert findings[0].details["is_negative"] is True
        assert findings[0].details["is_zero"] is False


def test_subtotal_negative_includes_currency_when_present() -> None:
    invoice = _invoice(subtotal="-75.00", currency="EUR")
    findings = check_non_positive_subtotal(invoice)

    assert len(findings) == 1
    assert findings[0].details["currency"] == "EUR"


# ---------------------------------------------------------------------------
# check_negative_tax: non-triggering and triggering paths
# ---------------------------------------------------------------------------


def test_tax_no_finding_when_absent() -> None:
    invoice = _invoice(tax=None)
    assert check_negative_tax(invoice) == []


def test_tax_no_finding_when_zero() -> None:
    for raw in ("0", "0.00", "0.000000", Decimal(0), Decimal("-0.00")):
        invoice = _invoice(tax=raw)
        assert check_negative_tax(invoice) == []


def test_tax_no_finding_when_positive() -> None:
    for raw in ("0.01", "0.000001", "15.00", "999999.99"):
        invoice = _invoice(tax=raw)
        assert check_negative_tax(invoice) == []


def test_tax_finding_when_negative() -> None:
    invoice = _invoice(tax="-15.00")
    findings = check_negative_tax(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "negative_tax"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "invoice.tax >= 0"
    assert finding.observed_value == "-15.00"
    assert finding.expected_value == ">= 0.00"
    assert "negative" in finding.explanation.lower()
    assert finding.details == {
        "field": "tax",
        "tax": "-15.00",
        "is_negative": True,
    }


def test_tax_finding_when_minimal_and_micro_negative() -> None:
    for raw in ("-0.01", "-0.000001", "-50000.00"):
        invoice = _invoice(tax=raw)
        findings = check_negative_tax(invoice)
        assert len(findings) == 1
        assert findings[0].finding_type == "negative_tax"
        assert findings[0].severity == "high"


def test_tax_negative_includes_currency_when_present() -> None:
    invoice = _invoice(tax="-12.50", currency="GBP")
    findings = check_negative_tax(invoice)

    assert len(findings) == 1
    assert findings[0].details["currency"] == "GBP"


# ---------------------------------------------------------------------------
# check_invalid_discount: negative discount tests
# ---------------------------------------------------------------------------


def test_discount_no_finding_when_absent() -> None:
    invoice = _invoice(discount=None)
    assert check_invalid_discount(invoice) == []


def test_discount_no_finding_when_zero() -> None:
    for raw in ("0", "0.00", "0.000000", Decimal(0), Decimal("-0.00")):
        invoice = _invoice(discount=raw)
        assert check_invalid_discount(invoice) == []


def test_discount_finding_when_negative() -> None:
    invoice = _invoice(discount="-10.00")
    findings = check_invalid_discount(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "invalid_discount"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "invoice.discount >= 0"
    assert finding.observed_value == "-10.00"
    assert finding.expected_value == ">= 0.00"
    assert "negative" in finding.explanation.lower()
    assert finding.details == {
        "field": "discount",
        "discount": "-10.00",
        "reason": "negative_discount",
        "is_negative": True,
    }


def test_discount_finding_when_minimal_and_micro_negative() -> None:
    for raw in ("-0.01", "-0.000001", "-25000.00"):
        invoice = _invoice(discount=raw)
        findings = check_invalid_discount(invoice)
        assert len(findings) == 1
        assert findings[0].finding_type == "invalid_discount"
        assert findings[0].severity == "high"
        assert findings[0].details["reason"] == "negative_discount"


def test_discount_negative_includes_currency_when_present() -> None:
    invoice = _invoice(discount="-5.00", currency="USD")
    findings = check_invalid_discount(invoice)

    assert len(findings) == 1
    assert findings[0].details["currency"] == "USD"


# ---------------------------------------------------------------------------
# check_invalid_discount: discount exceeding subtotal tests
# ---------------------------------------------------------------------------


def test_discount_no_finding_when_less_than_subtotal() -> None:
    invoice = _invoice(subtotal="100.00", discount="20.00")
    assert check_invalid_discount(invoice) == []


def test_discount_no_finding_when_equal_to_subtotal() -> None:
    invoice = _invoice(subtotal="100.00", discount="100.00")
    assert check_invalid_discount(invoice) == []


def test_discount_no_finding_when_subtotal_is_absent() -> None:
    invoice = _invoice(subtotal=None, discount="50.00")
    assert check_invalid_discount(invoice) == []


def test_discount_exceeding_subtotal_ignored_when_subtotal_is_zero_or_negative() -> (
    None
):
    for raw_subtotal in ("0.00", "-50.00"):
        invoice = _invoice(subtotal=raw_subtotal, discount="10.00")
        assert check_invalid_discount(invoice) == []


def test_discount_finding_when_exceeds_subtotal() -> None:
    invoice = _invoice(subtotal="100.00", discount="125.00")
    findings = check_invalid_discount(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "invalid_discount"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "invoice.discount <= invoice.subtotal"
    assert finding.observed_value == "125.00"
    assert finding.expected_value == "<= 100.00"
    assert "exceeds" in finding.explanation.lower()
    assert finding.details == {
        "field": "discount",
        "discount": "125.00",
        "subtotal": "100.00",
        "reason": "discount_exceeds_subtotal",
        "is_negative": False,
    }


def test_discount_finding_when_slightly_exceeds_subtotal() -> None:
    invoice = _invoice(subtotal="100.00", discount="100.01")
    findings = check_invalid_discount(invoice)

    assert len(findings) == 1
    assert findings[0].finding_type == "invalid_discount"
    assert findings[0].severity == "high"
    assert findings[0].details["reason"] == "discount_exceeds_subtotal"


def test_discount_finding_when_massively_exceeds_subtotal() -> None:
    invoice = _invoice(subtotal="50.00", discount="5000.00", currency="EUR")
    findings = check_invalid_discount(invoice)

    assert len(findings) == 1
    assert findings[0].details["currency"] == "EUR"
    assert findings[0].details["subtotal"] == "50.00"
    assert findings[0].details["discount"] == "5000.00"
