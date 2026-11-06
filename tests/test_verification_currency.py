"""Deterministic ISO 4217 currency code verification tests."""

from __future__ import annotations

import copy
from decimal import Decimal

import pytest

from veridoc.extraction.models import InvoiceExtraction, InvoiceLineItem
from veridoc.verification.currency import (
    ISO_4217_CURRENCY_CODES,
    check_currency_code,
)


def _invoice(**kwargs: object) -> InvoiceExtraction:
    """Build a minimal InvoiceExtraction with overridable keyword arguments."""
    defaults: dict[str, object] = {
        "document_type": "invoice",
        "vendor_name": "Acme Corp",
        "invoice_number": "INV-2026-001",
        "total": Decimal("100.00"),
    }
    defaults.update(kwargs)
    return InvoiceExtraction(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Valid Currencies
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "valid_code",
    [
        "USD",
        "EUR",
        "GBP",
        "JPY",
        "CAD",
        "AUD",
        "CHF",
        "SEK",
        "NOK",
        "NZD",
        "SGD",
        "HKD",
        "INR",
        "BRL",
        "ZAR",
        "DKK",
        "PLN",
        "ILS",
        "AED",
        "SAR",
    ],
)
def test_valid_currency_codes_produce_no_finding(valid_code: str) -> None:
    invoice = _invoice(currency=valid_code)
    assert check_currency_code(invoice) == []


def test_every_iso_4217_table_entry_produces_no_finding() -> None:
    for code in ISO_4217_CURRENCY_CODES:
        invoice = _invoice(currency=code)
        assert check_currency_code(invoice) == []


@pytest.mark.parametrize(
    "raw_code",
    [
        "usd",
        "eur",
        " gbp ",
        "  jpy  ",
    ],
)
def test_valid_currency_normalizes_case_and_whitespace(raw_code: str) -> None:
    invoice = InvoiceExtraction.model_construct(
        document_type="invoice",
        vendor_name="Acme Corp",
        invoice_number="INV-2026-001",
        currency=raw_code,
    )
    assert check_currency_code(invoice) == []


# ---------------------------------------------------------------------------
# Absent / Blank Currency
# ---------------------------------------------------------------------------


def test_absent_currency_produces_no_finding() -> None:
    invoice = _invoice(currency=None)
    assert check_currency_code(invoice) == []


def test_empty_currency_produces_no_finding() -> None:
    invoice = InvoiceExtraction.model_construct(
        document_type="invoice",
        currency="",
    )
    assert check_currency_code(invoice) == []


def test_whitespace_currency_produces_no_finding() -> None:
    invoice = InvoiceExtraction.model_construct(
        document_type="invoice",
        currency="   ",
    )
    assert check_currency_code(invoice) == []


# ---------------------------------------------------------------------------
# Invalid / Unrecognized Currencies
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("invalid_code", "normalized_code"),
    [
        ("XYZ", "XYZ"),
        ("INV", "INV"),
        ("FOO", "FOO"),
        ("BAR", "BAR"),
        ("ZZZ", "ZZZ"),
        ("DLR", "DLR"),
        ("ABC", "ABC"),
        ("TOT", "TOT"),
    ],
)
def test_invalid_currency_code_produces_medium_finding(
    invalid_code: str, normalized_code: str
) -> None:
    invoice = _invoice(currency=invalid_code)
    findings = check_currency_code(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "invalid_currency"
    assert finding.severity == "medium"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "currency in ISO 4217 active alphabetic codes"
    assert finding.observed_value == normalized_code
    assert finding.expected_value == "valid ISO 4217 currency code"
    assert finding.details == {"field": "currency", "currency": normalized_code}
    assert normalized_code in finding.explanation


def test_invalid_constructed_currency_normalizes_details() -> None:
    invoice = InvoiceExtraction.model_construct(
        document_type="invoice",
        currency=" foo ",
    )
    findings = check_currency_code(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "invalid_currency"
    assert finding.observed_value == "FOO"
    assert finding.details == {"field": "currency", "currency": "FOO"}


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


def test_check_currency_code_preserves_input_immutability() -> None:
    invoice = _invoice(
        currency="XYZ",
        line_items=[
            InvoiceLineItem(
                description="Consulting Services",
                quantity=Decimal(1),
                unit_price=Decimal("100.00"),
                total_price=Decimal("100.00"),
            )
        ],
    )
    original_dict = copy.deepcopy(invoice.model_dump())

    findings = check_currency_code(invoice)

    assert len(findings) == 1
    assert invoice.model_dump() == original_dict
    assert invoice.currency == "XYZ"
