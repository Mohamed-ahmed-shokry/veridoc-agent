"""Tests for deterministic excessive tax amount verification."""

from __future__ import annotations

from decimal import Decimal

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.tax_bounds import (
    DEFAULT_MAX_TAX_TO_SUBTOTAL_RATIO,
    check_excessive_tax,
)


def _invoice(
    *,
    subtotal: Decimal | None = None,
    tax: Decimal | None = None,
    total: Decimal | None = None,
    currency: str | None = "USD",
) -> InvoiceExtraction:
    return InvoiceExtraction(
        document_type="invoice",
        currency=currency,
        subtotal=subtotal,
        tax=tax,
        total=total,
    )


def test_check_excessive_tax_passes_on_valid_tax_proportions() -> None:
    # Zero tax (exempt / zero-rated)
    assert (
        check_excessive_tax(_invoice(subtotal=Decimal("100.00"), tax=Decimal("0.00")))
        == []
    )
    # Standard VAT rates: 5%, 19%, 20%, 27%
    assert (
        check_excessive_tax(_invoice(subtotal=Decimal("100.00"), tax=Decimal("5.00")))
        == []
    )
    assert (
        check_excessive_tax(_invoice(subtotal=Decimal("100.00"), tax=Decimal("19.00")))
        == []
    )
    assert (
        check_excessive_tax(_invoice(subtotal=Decimal("100.00"), tax=Decimal("20.00")))
        == []
    )
    assert (
        check_excessive_tax(_invoice(subtotal=Decimal("100.00"), tax=Decimal("27.00")))
        == []
    )
    # Exact boundary condition: 100% tax is permitted by default
    assert (
        check_excessive_tax(_invoice(subtotal=Decimal("100.00"), tax=Decimal("100.00")))
        == []
    )


def test_check_excessive_tax_triggers_when_tax_exceeds_subtotal() -> None:
    invoice = _invoice(
        subtotal=Decimal("100.00"),
        tax=Decimal("150.00"),
        total=Decimal("250.00"),
        currency="USD",
    )
    findings = check_excessive_tax(invoice)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "excessive_tax"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "invoice.tax <= invoice.subtotal"
    assert finding.observed_value == "150.00"
    assert finding.expected_value == "<= 100.00"
    assert finding.details == {
        "field": "tax",
        "tax": "150.00",
        "subtotal": "100.00",
        "effective_tax_rate": "1.5000",
        "max_tax_rate": "1.00",
        "currency": "USD",
    }
    assert "exceeds the pre-tax subtotal" in finding.explanation


def test_check_excessive_tax_triggers_when_tax_exceeds_total_with_omitted_subtotal() -> (
    None
):
    invoice = _invoice(
        subtotal=None,
        tax=Decimal("250.00"),
        total=Decimal("200.00"),
        currency="EUR",
    )
    findings = check_excessive_tax(invoice)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "excessive_tax"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "invoice.tax <= invoice.total"
    assert finding.observed_value == "250.00"
    assert finding.expected_value == "<= 200.00"
    assert finding.details == {
        "field": "tax",
        "tax": "250.00",
        "total": "200.00",
        "currency": "EUR",
    }
    assert "exceeds the payable invoice total" in finding.explanation


def test_check_excessive_tax_passes_when_tax_equals_total_with_omitted_subtotal() -> (
    None
):
    invoice = _invoice(subtotal=None, tax=Decimal("200.00"), total=Decimal("200.00"))
    assert check_excessive_tax(invoice) == []


def test_check_excessive_tax_passes_on_absent_tax() -> None:
    assert check_excessive_tax(_invoice(tax=None, subtotal=Decimal("100.00"))) == []


def test_check_excessive_tax_passes_on_negative_or_zero_tax() -> None:
    assert (
        check_excessive_tax(_invoice(tax=Decimal("-15.00"), subtotal=Decimal("100.00")))
        == []
    )
    assert (
        check_excessive_tax(_invoice(tax=Decimal("0.00"), subtotal=Decimal("100.00")))
        == []
    )


def test_check_excessive_tax_passes_on_non_positive_subtotal_or_total() -> None:
    # Zero or negative subtotal is handled by check_non_positive_subtotal
    assert (
        check_excessive_tax(_invoice(subtotal=Decimal("0.00"), tax=Decimal("50.00")))
        == []
    )
    assert (
        check_excessive_tax(_invoice(subtotal=Decimal("-100.00"), tax=Decimal("50.00")))
        == []
    )
    # Zero or negative total when subtotal is None is handled by check_non_positive_invoice_total
    assert (
        check_excessive_tax(
            _invoice(subtotal=None, total=Decimal("0.00"), tax=Decimal("50.00"))
        )
        == []
    )
    assert (
        check_excessive_tax(
            _invoice(subtotal=None, total=Decimal("-50.00"), tax=Decimal("50.00"))
        )
        == []
    )
    # Both subtotal and total are None
    assert (
        check_excessive_tax(_invoice(subtotal=None, total=None, tax=Decimal("50.00")))
        == []
    )


def test_check_excessive_tax_supports_custom_max_tax_rate() -> None:
    # Subtotal 100 with tax 35 exceeds 30% max tax rate
    invoice = _invoice(subtotal=Decimal("100.00"), tax=Decimal("35.00"), currency=None)
    findings = check_excessive_tax(invoice, max_tax_rate=Decimal("0.30"))
    assert len(findings) == 1
    assert findings[0].expected_value == "<= 30.0000"
    assert findings[0].deterministic_rule == "invoice.tax <= invoice.subtotal * 0.30"
    assert findings[0].details["effective_tax_rate"] == "0.3500"
    assert "currency" not in findings[0].details

    # Subtotal 100 with tax 25 does not exceed 30% max tax rate
    invoice_ok = _invoice(subtotal=Decimal("100.00"), tax=Decimal("25.00"))
    assert check_excessive_tax(invoice_ok, max_tax_rate=Decimal("0.30")) == []


def test_check_excessive_tax_preserves_input_immutability() -> None:
    invoice = _invoice(
        subtotal=Decimal("100.00"),
        tax=Decimal("150.00"),
        total=Decimal("250.00"),
        currency="USD",
    )
    dump_before = invoice.model_dump()
    check_excessive_tax(invoice)
    assert invoice.model_dump() == dump_before
    assert DEFAULT_MAX_TAX_TO_SUBTOTAL_RATIO == Decimal("1.00")
