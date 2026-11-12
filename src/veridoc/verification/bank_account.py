"""Deterministic IBAN structure and checksum verification for vendor bank accounts.

The vendor registry rules compare an extracted bank account with registered
accounts, but they are silent for unregistered vendors or vendors without a
registered account. A corrupted or fabricated IBAN would then pass every
deterministic rule. ISO 13616 IBANs carry a country-specific length and an
ISO 7064 mod-97-10 checksum, so a structurally impossible IBAN can be rejected
without reference data (ADR 0041).

Only IBAN-shaped values with a known country prefix are evaluated. Domestic
account numbers and free text are intentionally ignored.
"""

from __future__ import annotations

import re
from typing import Final

from veridoc.extraction.models import InvoiceExtraction
from veridoc.vendors.models import normalize_bank_account
from veridoc.verification.models import VerificationFinding

_IBAN_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]+$")

IBAN_COUNTRY_LENGTHS: Final[dict[str, int]] = {
    "AD": 24,
    "AE": 23,
    "AL": 28,
    "AT": 20,
    "AZ": 28,
    "BA": 20,
    "BE": 16,
    "BG": 22,
    "BH": 22,
    "BR": 29,
    "BY": 28,
    "CH": 21,
    "CR": 22,
    "CY": 28,
    "CZ": 24,
    "DE": 22,
    "DK": 18,
    "DO": 28,
    "EE": 20,
    "EG": 29,
    "ES": 24,
    "FI": 18,
    "FO": 18,
    "FR": 27,
    "GB": 22,
    "GE": 22,
    "GI": 23,
    "GL": 18,
    "GR": 27,
    "GT": 28,
    "HR": 21,
    "HU": 28,
    "IE": 22,
    "IL": 23,
    "IQ": 23,
    "IS": 26,
    "IT": 27,
    "JO": 30,
    "KW": 30,
    "KZ": 20,
    "LB": 28,
    "LC": 32,
    "LI": 21,
    "LT": 20,
    "LU": 20,
    "LV": 21,
    "MC": 27,
    "MD": 24,
    "ME": 22,
    "MK": 19,
    "MR": 27,
    "MT": 31,
    "MU": 30,
    "NL": 18,
    "NO": 15,
    "PK": 24,
    "PL": 28,
    "PS": 29,
    "PT": 25,
    "QA": 29,
    "RO": 24,
    "RS": 22,
    "SA": 24,
    "SC": 31,
    "SE": 24,
    "SI": 19,
    "SK": 24,
    "SM": 27,
    "ST": 25,
    "SV": 28,
    "TL": 23,
    "TN": 24,
    "TR": 26,
    "UA": 29,
    "VA": 22,
    "VG": 24,
    "XK": 20,
}


def iban_checksum_is_valid(iban: str) -> bool:
    """Return whether a normalized IBAN satisfies the ISO 7064 mod-97-10 check.

    The first four characters move to the end, letters become two-digit numbers
    (``A`` is 10), and the resulting integer must leave a remainder of 1.
    """
    rearranged = iban[4:] + iban[:4]
    digits = "".join(str(int(character, 36)) for character in rearranged)
    return int(digits) % 97 == 1


def check_bank_account_checksum(
    invoice: InvoiceExtraction,
) -> list[VerificationFinding]:
    """Verify IBAN length and checksum for extracted vendor bank accounts.

    Returns an empty list when:
    - ``invoice.vendor_bank_account`` is absent or blank;
    - the normalized value does not match IBAN structure or uses an unknown country code;
    - the normalized value matches the country length and satisfies the mod-97 check.

    Returns a list with one ``invalid_bank_account`` finding (severity="high")
    when:
    - the account is IBAN-shaped but its length does not equal the expected country length (reason="length");
    - the account is IBAN-shaped and has the correct length, but fails the mod-97 check (reason="checksum").
    """
    if not invoice.vendor_bank_account:
        return []

    account = normalize_bank_account(invoice.vendor_bank_account)
    if not account:
        return []

    if not _IBAN_PATTERN.match(account):
        return []

    country_code = account[:2]
    expected_length = IBAN_COUNTRY_LENGTHS.get(country_code)
    if expected_length is None:
        return []

    if len(account) != expected_length:
        return [
            VerificationFinding(
                finding_type="invalid_bank_account",
                severity="high",
                explanation=(
                    f"The vendor bank account '{account}' has {len(account)} characters, but "
                    f"{country_code} IBANs require {expected_length} characters."
                ),
                comparison_source="invoice_fields",
                deterministic_rule="len(IBAN) == expected_country_length",
                observed_value=account,
                expected_value=f"{expected_length} characters",
                details={
                    "field": "vendor_bank_account",
                    "account": account,
                    "reason": "length",
                },
            )
        ]

    if not iban_checksum_is_valid(account):
        return [
            VerificationFinding(
                finding_type="invalid_bank_account",
                severity="high",
                explanation=(
                    f"The vendor bank account '{account}' fails its IBAN checksum."
                ),
                comparison_source="invoice_fields",
                deterministic_rule="IBAN mod-97 remainder == 1",
                observed_value=account,
                expected_value=None,
                details={
                    "field": "vendor_bank_account",
                    "account": account,
                    "reason": "checksum",
                },
            )
        ]

    return []


__all__ = [
    "IBAN_COUNTRY_LENGTHS",
    "check_bank_account_checksum",
    "iban_checksum_is_valid",
]
