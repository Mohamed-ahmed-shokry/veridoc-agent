"""Tests for cross-field vendor tax identifier and bank account country consistency verification."""

from __future__ import annotations

import copy
import pytest

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.country_consistency import (
    check_tax_id_bank_country_consistency,
)


def _invoice(
    tax_id: str | None = None,
    bank_account: str | None = None,
) -> InvoiceExtraction:
    return InvoiceExtraction(
        document_type="invoice",
        vendor_tax_id=tax_id,
        vendor_bank_account=bank_account,
    )


@pytest.mark.parametrize(
    ("tax_id", "bank_account"),
    [
        # Matching EU countries
        ("DE123456789", "DE89370400440532013000"),
        ("FR12345678901", "FR1420041010050500013M02606"),
        ("IT12345678901", "IT60X0542811101000000123456"),
        ("GB123456789", "GB29NWBK60161331926819"),
        ("ESX1234567X", "ES9121000418450200051332"),
        # Spacing and formatting variations
        (" DE 123 456 789 ", " DE89 3704 0044 0532 0130 00 "),
        ("de123456789", "de89370400440532013000"),
        # Geographic equivalents
        ("EL123456789", "GR1601101250000000012300505"),  # Greece: EL VAT <-> GR IBAN
        ("XI123456789", "GB29NWBK60161331926819"),  # Northern Ireland: XI VAT <-> GB IBAN
    ],
)
def test_country_consistency_accepts_matching_and_equivalent_countries(
    tax_id: str,
    bank_account: str,
) -> None:
    invoice = _invoice(tax_id=tax_id, bank_account=bank_account)
    assert check_tax_id_bank_country_consistency(invoice) == []


@pytest.mark.parametrize(
    ("tax_id", "bank_account"),
    [
        (None, "DE89370400440532013000"),
        ("DE123456789", None),
        (None, None),
        ("", "DE89370400440532013000"),
        ("DE123456789", ""),
        ("   ", "DE89370400440532013000"),
        ("DE123456789", "   "),
        # Unrecognized prefix in tax ID (e.g. US domestic EIN)
        ("12-3456789", "DE89370400440532013000"),
        # Domestic non-IBAN bank account
        ("DE123456789", "1234567890"),
    ],
)
def test_country_consistency_accepts_absent_blank_or_unrecognized_schemes(
    tax_id: str | None,
    bank_account: str | None,
) -> None:
    invoice = _invoice(tax_id=tax_id, bank_account=bank_account)
    assert check_tax_id_bank_country_consistency(invoice) == []


def test_country_consistency_flags_mismatched_countries() -> None:
    # German VAT with Cyprus IBAN (classic invoice redirection pattern)
    invoice = _invoice(
        tax_id="DE123456789",
        bank_account="CY17002001280000001201234567",
    )
    findings = check_tax_id_bank_country_consistency(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "tax_id_bank_country_mismatch"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "tax_country == bank_country"
    assert finding.observed_value == "CY"
    assert finding.expected_value == "DE"
    assert finding.details == {
        "field": "vendor_bank_account",
        "tax_country": "DE",
        "bank_country": "CY",
        "vendor_tax_id": "DE123456789",
        "vendor_bank_account": "CY17002001280000001201234567",
    }


def test_country_consistency_flags_french_vat_with_malta_iban() -> None:
    invoice = _invoice(
        tax_id="FR12345678901",
        bank_account="MT12VALL22013000000012345678901",
    )
    findings = check_tax_id_bank_country_consistency(invoice)

    assert len(findings) == 1
    assert findings[0].finding_type == "tax_id_bank_country_mismatch"
    assert findings[0].details["tax_country"] == "FR"
    assert findings[0].details["bank_country"] == "MT"


def test_country_consistency_does_not_mutate_input() -> None:
    invoice = _invoice(
        tax_id="DE123456789",
        bank_account="CY17002001280000001201234567",
    )
    snapshot = copy.deepcopy(invoice)
    check_tax_id_bank_country_consistency(invoice)
    assert invoice == snapshot
