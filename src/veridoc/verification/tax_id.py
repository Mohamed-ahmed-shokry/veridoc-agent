"""Deterministic VAT identifier structure verification for vendor tax IDs.

The vendor registry tax-id rule only runs for a resolved vendor with registered
tax identifiers. An unregistered vendor could therefore present an OCR-corrupted
or fabricated VAT number that passes every deterministic rule. European VAT
numbers carry a country prefix and a published per-country structure, so a
structurally impossible number can be rejected without reference data or
network access (ADR 0042).

Only identifiers with a recognized country prefix are evaluated. Domestic and
non-European identifier schemes are intentionally ignored, and checksum
algorithms are out of scope.
"""

from __future__ import annotations

import re
from typing import Final

from veridoc.extraction.models import InvoiceExtraction
from veridoc.vendors.models import normalize_tax_id
from veridoc.verification.models import VerificationFinding

_IRISH_OLD_FORMAT: Final[str] = r"\d[A-Z+*]\d{5}[A-Z]"
_UK_NUMBER: Final[str] = r"\d{9}|\d{12}|GD\d{3}|HA\d{3}"

VAT_STRUCTURES: Final[dict[str, re.Pattern[str]]] = {
    prefix: re.compile(pattern)
    for prefix, pattern in {
        "AT": r"U\d{8}",
        "BE": r"[01]\d{9}",
        "BG": r"\d{9,10}",
        "CY": r"\d{8}[A-Z]",
        "CZ": r"\d{8,10}",
        "DE": r"\d{9}",
        "DK": r"\d{8}",
        "EE": r"\d{9}",
        "EL": r"\d{9}",
        "ES": r"[A-Z0-9]\d{7}[A-Z0-9]",
        "FI": r"\d{8}",
        "FR": r"[A-Z0-9]{2}\d{9}",
        "GB": _UK_NUMBER,
        "HR": r"\d{11}",
        "HU": r"\d{8}",
        "IE": rf"\d{{7}}[A-Z]{{1,2}}|{_IRISH_OLD_FORMAT}",
        "IT": r"\d{11}",
        "LT": r"\d{9}|\d{12}",
        "LU": r"\d{8}",
        "LV": r"\d{11}",
        "MT": r"\d{8}",
        "NL": r"\d{9}B\d{2}",
        "PL": r"\d{10}",
        "PT": r"\d{9}",
        "RO": r"\d{2,10}",
        "SE": r"\d{12}",
        "SI": r"\d{8}",
        "SK": r"\d{10}",
        "XI": _UK_NUMBER,
    }.items()
}


def check_tax_id_format(invoice: InvoiceExtraction) -> list[VerificationFinding]:
    """Verify the VAT structure of an extracted vendor tax identifier.

    Returns an empty list when:
    - ``invoice.vendor_tax_id`` is absent or blank;
    - the normalized value has no recognized country prefix;
    - the remainder matches the structure for its country prefix.

    Returns one ``invalid_tax_id`` finding (severity="medium") when the prefix
    is recognized but the remainder does not match the country structure.
    """
    if not invoice.vendor_tax_id:
        return []

    tax_id = normalize_tax_id(invoice.vendor_tax_id)
    country = tax_id[:2]
    structure = VAT_STRUCTURES.get(country)
    if structure is None or structure.fullmatch(tax_id[2:]):
        return []

    return [
        VerificationFinding(
            finding_type="invalid_tax_id",
            severity="medium",
            explanation=(
                f"The vendor tax identifier '{tax_id}' does not match the "
                f"{country} VAT number structure."
            ),
            comparison_source="invoice_fields",
            deterministic_rule="vendor_tax_id matches the country VAT structure",
            observed_value=tax_id,
            expected_value=None,
            details={
                "field": "vendor_tax_id",
                "tax_id": tax_id,
                "country": country,
            },
        )
    ]


__all__ = ["VAT_STRUCTURES", "check_tax_id_format"]
