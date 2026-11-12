"""Deterministic cross-field consistency verification between vendor tax ID and bank account.

In invoice redirection and fraud attacks, bad actors frequently forge legitimate vendor
tax credentials (e.g., German DE or French FR VAT numbers) while directing payment to
offshore accounts in unrelated jurisdictions (e.g., Cyprus CY or Malta MT).
This rule deterministically compares the 2-letter country prefix from the extracted
vendor VAT identifier against the 2-letter IBAN country prefix from the extracted
vendor bank account, accounting for standard geographic equivalents (e.g., EL <-> GR,
XI <-> GB).
"""

from __future__ import annotations

from typing import Final

from veridoc.extraction.models import InvoiceExtraction
from veridoc.vendors.models import normalize_bank_account, normalize_tax_id
from veridoc.verification.bank_account import IBAN_COUNTRY_LENGTHS
from veridoc.verification.models import VerificationFinding
from veridoc.verification.tax_id import VAT_STRUCTURES

# Canonical mappings for country equivalents between VAT and IBAN schemes
_CANONICAL_COUNTRY_MAP: Final[dict[str, str]] = {
    "EL": "GR",  # Greek VAT prefix is EL, IBAN country is GR
    "XI": "GB",  # Northern Ireland VAT prefix under Brexit protocol is XI, IBAN is GB
}


def _canonical_country(code: str) -> str:
    return _CANONICAL_COUNTRY_MAP.get(code, code)


def check_tax_id_bank_country_consistency(
    invoice: InvoiceExtraction,
) -> list[VerificationFinding]:
    """Verify geographic concordance between vendor tax ID and bank account country prefixes.

    Returns an empty list when:
    - ``vendor_tax_id`` or ``vendor_bank_account`` is absent or blank;
    - either prefix is unrecognized in its respective table (VAT_STRUCTURES / IBAN_COUNTRY_LENGTHS);
    - canonical country codes match (including equivalents: EL/GR, XI/GB).

    Returns one ``tax_id_bank_country_mismatch`` finding (severity="high") when
    recognized country prefixes represent different jurisdictions.
    """
    if not invoice.vendor_tax_id or not invoice.vendor_bank_account:
        return []

    tax_id = normalize_tax_id(invoice.vendor_tax_id)
    bank_account = normalize_bank_account(invoice.vendor_bank_account)

    if len(tax_id) < 2 or len(bank_account) < 2:
        return []

    tax_country_raw = tax_id[:2]
    bank_country_raw = bank_account[:2]

    # Only evaluate when both prefixes are recognized standard country prefixes
    if (
        tax_country_raw not in VAT_STRUCTURES
        or bank_country_raw not in IBAN_COUNTRY_LENGTHS
    ):
        return []

    canonical_tax_country = _canonical_country(tax_country_raw)
    canonical_bank_country = _canonical_country(bank_country_raw)

    if canonical_tax_country == canonical_bank_country:
        return []

    return [
        VerificationFinding(
            finding_type="tax_id_bank_country_mismatch",
            severity="high",
            explanation=(
                f"Vendor tax identifier country '{tax_country_raw}' does not match "
                f"bank account IBAN country '{bank_country_raw}'."
            ),
            comparison_source="invoice_fields",
            deterministic_rule="tax_country == bank_country",
            observed_value=bank_country_raw,
            expected_value=tax_country_raw,
            details={
                "field": "vendor_bank_account",
                "tax_country": tax_country_raw,
                "bank_country": bank_country_raw,
                "vendor_tax_id": tax_id,
                "vendor_bank_account": bank_account,
            },
        )
    ]


__all__ = ["check_tax_id_bank_country_consistency"]
