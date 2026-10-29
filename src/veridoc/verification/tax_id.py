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

__all__ = ["VAT_STRUCTURES"]
