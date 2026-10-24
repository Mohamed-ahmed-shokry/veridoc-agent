"""Phase 35 IBAN checksum helper tests (ADR 0041)."""

from __future__ import annotations

import pytest

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.bank_account import (
    IBAN_COUNTRY_LENGTHS,
    check_bank_account_checksum,
    iban_checksum_is_valid,
)


def _invoice(bank_account: str | None) -> InvoiceExtraction:
    return InvoiceExtraction(
        document_type="invoice",
        vendor_bank_account=bank_account,
    )


@pytest.mark.parametrize(
    "iban",
    [
        "GB82WEST12345698765432",
        "DE89370400440532013000",
        "FR1420041010050500013M02606",
        "NO9386011117947",
        "BE68539007547034",
    ],
)
def test_iban_checksum_accepts_published_example_ibans(iban: str) -> None:
    assert iban_checksum_is_valid(iban)


@pytest.mark.parametrize(
    "iban",
    [
        "GB82WEST12345698765433",
        "DE89370400440532013001",
        "FR1420041010050500013M02607",
        "NO9386011117948",
        "BE68539007547035",
    ],
)
def test_iban_checksum_rejects_single_digit_corruption(iban: str) -> None:
    assert not iban_checksum_is_valid(iban)


def test_iban_checksum_rejects_swapped_adjacent_digits() -> None:
    assert not iban_checksum_is_valid("GB82WEST12345698765342")


def test_iban_length_table_matches_published_example_lengths() -> None:
    assert IBAN_COUNTRY_LENGTHS["GB"] == len("GB82WEST12345698765432")
    assert IBAN_COUNTRY_LENGTHS["DE"] == len("DE89370400440532013000")
    assert IBAN_COUNTRY_LENGTHS["FR"] == len("FR1420041010050500013M02606")
    assert IBAN_COUNTRY_LENGTHS["NO"] == len("NO9386011117947")
    assert IBAN_COUNTRY_LENGTHS["BE"] == len("BE68539007547034")


@pytest.mark.parametrize("account", [None, "", "   ", "\t\n"])
def test_bank_account_checksum_accepts_absent_and_blank(account: str | None) -> None:
    assert check_bank_account_checksum(_invoice(account)) == []


@pytest.mark.parametrize(
    "account",
    [
        "12345678",
        "00-11-22-33",
        "ACCOUNT_999",
        "US1234567890",
        "ZZ991234567890",
    ],
)
def test_bank_account_checksum_accepts_non_iban_accounts(account: str) -> None:
    assert check_bank_account_checksum(_invoice(account)) == []


@pytest.mark.parametrize(
    "account",
    [
        "GB82WEST12345698765432",
        "GB82 WEST 1234 5698 7654 32",
        "gb82west12345698765432",
        "GB82-WEST.1234-5698-7654-32",
        "DE89 3704 0044 0532 0130 00",
        "FR14 2004 1010 0505 0001 3M02 606",
    ],
)
def test_bank_account_checksum_accepts_valid_ibans(account: str) -> None:
    assert check_bank_account_checksum(_invoice(account)) == []


def test_bank_account_checksum_flags_short_iban() -> None:
    findings = check_bank_account_checksum(_invoice("GB82WEST1234569876543"))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "invalid_bank_account"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_fields"
    assert finding.observed_value == "GB82WEST1234569876543"
    assert finding.expected_value == "22 characters"
    assert finding.details == {
        "field": "vendor_bank_account",
        "account": "GB82WEST1234569876543",
        "reason": "length",
    }


def test_bank_account_checksum_flags_long_iban() -> None:
    findings = check_bank_account_checksum(_invoice("GB82WEST123456987654321"))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "invalid_bank_account"
    assert finding.severity == "high"
    assert finding.details["reason"] == "length"


def test_bank_account_checksum_flags_checksum_mismatch() -> None:
    findings = check_bank_account_checksum(_invoice("GB82WEST12345698765433"))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "invalid_bank_account"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_fields"
    assert finding.observed_value == "GB82WEST12345698765433"
    assert finding.expected_value is None
    assert finding.details == {
        "field": "vendor_bank_account",
        "account": "GB82WEST12345698765433",
        "reason": "checksum",
    }


def test_bank_account_checksum_preserves_input_immutability() -> None:
    invoice = _invoice("GB82 WEST 1234 5698 7654 33")
    snapshot = invoice.model_dump()
    check_bank_account_checksum(invoice)
    assert invoice.model_dump() == snapshot
