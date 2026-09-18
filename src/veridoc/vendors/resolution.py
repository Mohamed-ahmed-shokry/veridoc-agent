"""Deterministic multi-attribute vendor entity resolution engine."""

from __future__ import annotations

import difflib
import re

from veridoc.extraction.models import InvoiceExtraction
from veridoc.vendors.models import (
    VendorEntity,
    VendorResolutionResult,
    derive_canonical_vendor_key,
    normalize_bank_account,
    normalize_tax_id,
)
from veridoc.vendors.protocol import VendorRepository

_WORD_PATTERN = re.compile(r"\w+")


def sorted_token_string(value: str) -> str:
    """Return lowercase alphanumeric tokens sorted and space-separated."""
    tokens = _WORD_PATTERN.findall(value.lower())
    return " ".join(sorted(tokens))


def calculate_token_similarity(name1: str, name2: str) -> float:
    """Return deterministic token set sequence similarity in [0.0, 1.0]."""
    s1 = sorted_token_string(name1)
    s2 = sorted_token_string(name2)
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0
    return difflib.SequenceMatcher(None, s1, s2).ratio()


def resolve_vendor(
    invoice: InvoiceExtraction,
    repository: VendorRepository,
    *,
    fuzzy_threshold: float = 0.85,
) -> VendorResolutionResult:
    """Deterministically resolve an extracted invoice against vendor master data."""
    # Priority 1: Exact Tax/VAT ID Match
    if invoice.vendor_tax_id:
        clean_tax = normalize_tax_id(invoice.vendor_tax_id)
        if clean_tax:
            tax_matches = repository.find_vendors_by_tax_id(clean_tax)
            if len(tax_matches) == 1:
                vendor = tax_matches[0]
                return VendorResolutionResult(
                    resolved_vendor_id=vendor.vendor_id,
                    canonical_key=vendor.canonical_key,
                    legal_name=vendor.legal_name,
                    confidence="exact_tax",
                    score=1.0,
                    matched_attribute=f"tax_id:{clean_tax}",
                    status=vendor.status,
                )
            if len(tax_matches) > 1:
                return VendorResolutionResult(
                    confidence="unresolved",
                    score=0.0,
                    matched_attribute=f"ambiguous_tax_id:{clean_tax}",
                )

    # Priority 2: Exact Bank Account / IBAN Match
    if invoice.vendor_bank_account:
        clean_bank = normalize_bank_account(invoice.vendor_bank_account)
        if clean_bank:
            bank_matches = repository.find_vendors_by_bank_account(clean_bank)
            if len(bank_matches) == 1:
                vendor = bank_matches[0]
                return VendorResolutionResult(
                    resolved_vendor_id=vendor.vendor_id,
                    canonical_key=vendor.canonical_key,
                    legal_name=vendor.legal_name,
                    confidence="exact_bank",
                    score=1.0,
                    matched_attribute=f"bank_account:{clean_bank}",
                    status=vendor.status,
                )
            if len(bank_matches) > 1:
                return VendorResolutionResult(
                    confidence="unresolved",
                    score=0.0,
                    matched_attribute=f"ambiguous_bank_account:{clean_bank}",
                )

    # Priority 3: Exact Canonical Key or Registered Alias Match
    name_candidates = [
        val for val in (invoice.vendor_identifier, invoice.vendor_name) if val
    ]
    for raw_name in name_candidates:
        canonical = derive_canonical_vendor_key(raw_name)
        if not canonical:
            continue

        direct_vendor = repository.get_vendor_by_canonical_key(canonical)
        if direct_vendor is not None:
            return VendorResolutionResult(
                resolved_vendor_id=direct_vendor.vendor_id,
                canonical_key=direct_vendor.canonical_key,
                legal_name=direct_vendor.legal_name,
                confidence="exact_alias",
                score=1.0,
                matched_attribute=f"canonical_key:{canonical}",
                status=direct_vendor.status,
            )

        alias_matches = repository.find_vendors_by_alias(canonical)
        if len(alias_matches) == 1:
            vendor = alias_matches[0]
            return VendorResolutionResult(
                resolved_vendor_id=vendor.vendor_id,
                canonical_key=vendor.canonical_key,
                legal_name=vendor.legal_name,
                confidence="exact_alias",
                score=1.0,
                matched_attribute=f"alias:{canonical}",
                status=vendor.status,
            )
        if len(alias_matches) > 1:
            return VendorResolutionResult(
                confidence="unresolved",
                score=0.0,
                matched_attribute=f"ambiguous_alias:{canonical}",
            )

    # Priority 4: Bounded Token Set Similarity Match
    if name_candidates:
        all_vendors = repository.list_vendors()
        scored_candidates: list[tuple[float, VendorEntity, str]] = []

        for vendor in all_vendors:
            vendor_names = [vendor.legal_name, *vendor.aliases]
            best_vendor_score = 0.0
            best_matched_name = vendor.legal_name

            for extracted in name_candidates:
                for reg_name in vendor_names:
                    score = calculate_token_similarity(extracted, reg_name)
                    if score > best_vendor_score:
                        best_vendor_score = score
                        best_matched_name = reg_name

            if best_vendor_score >= fuzzy_threshold:
                scored_candidates.append((best_vendor_score, vendor, best_matched_name))

        if scored_candidates:
            scored_candidates.sort(key=lambda item: item[0], reverse=True)
            top_score, top_vendor, matched_name = scored_candidates[0]

            # Conflict check: if second candidate is within 0.01 of top score, treat as ambiguous
            if len(scored_candidates) > 1:
                second_score = scored_candidates[1][0]
                if abs(top_score - second_score) < 0.01:
                    return VendorResolutionResult(
                        confidence="unresolved",
                        score=round(top_score, 4),
                        matched_attribute=f"ambiguous_fuzzy:{matched_name}",
                    )

            return VendorResolutionResult(
                resolved_vendor_id=top_vendor.vendor_id,
                canonical_key=top_vendor.canonical_key,
                legal_name=top_vendor.legal_name,
                confidence="fuzzy_name",
                score=round(top_score, 4),
                matched_attribute=f"fuzzy_name:{matched_name}",
                status=top_vendor.status,
            )

    # Fallback: Unresolved
    return VendorResolutionResult(
        confidence="unresolved",
        score=0.0,
        matched_attribute=None,
    )
