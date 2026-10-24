"""Phase 35 IBAN checksum helper tests (ADR 0041)."""

from __future__ import annotations

import pytest

from veridoc.verification.bank_account import (
    IBAN_COUNTRY_LENGTHS,
    iban_checksum_is_valid,
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
