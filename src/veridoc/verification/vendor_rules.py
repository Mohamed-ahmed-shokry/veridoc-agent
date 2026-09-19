"""Deterministic verification rules for vendor identity and bank coordinates."""

from __future__ import annotations

from veridoc.extraction.models import InvoiceExtraction
from veridoc.vendors.models import (
    VendorEntity,
    VendorResolutionResult,
    normalize_bank_account,
    normalize_tax_id,
)
from veridoc.vendors.protocol import VendorRepository
from veridoc.vendors.resolution import resolve_vendor
from veridoc.verification.models import VerificationFinding


def check_vendor_registry(
    invoice: InvoiceExtraction,
    vendor_repository: VendorRepository | None,
) -> tuple[list[VerificationFinding], VendorResolutionResult | None]:
    """Run deterministic vendor and payment reconciliation checks against master data."""
    if vendor_repository is None:
        return [], None

    resolution = resolve_vendor(invoice, vendor_repository)
    vendor: VendorEntity | None = None
    if resolution.resolved_vendor_id:
        vendor = vendor_repository.get_vendor_by_id(resolution.resolved_vendor_id)

    findings: list[VerificationFinding] = []
    findings.extend(check_vendor_registration(resolution, invoice))
    findings.extend(check_vendor_status(resolution, vendor))
    findings.extend(check_vendor_bank_account(resolution, invoice, vendor))
    findings.extend(check_vendor_tax_id(resolution, invoice, vendor))
    return findings, resolution


def check_vendor_registration(
    resolution: VendorResolutionResult | None,
    invoice: InvoiceExtraction,
) -> list[VerificationFinding]:
    """Flag invoices from unregistered vendors."""
    if resolution is None or resolution.confidence != "unresolved":
        return []

    has_vendor_data = any(
        (
            invoice.vendor_name,
            invoice.vendor_identifier,
            invoice.vendor_tax_id,
            invoice.vendor_bank_account,
        )
    )
    if not has_vendor_data:
        return []

    vendor_label = invoice.vendor_name or invoice.vendor_identifier or "unnamed vendor"
    return [
        VerificationFinding(
            finding_type="unregistered_vendor",
            severity="medium",
            explanation=(
                f"The vendor '{vendor_label}' could not be matched to any "
                "registered supplier in the vendor master registry."
            ),
            comparison_source="vendor_registry",
            deterministic_rule="vendor entity resolution must match an approved vendor",
            details={
                "vendor_name": invoice.vendor_name,
                "vendor_identifier": invoice.vendor_identifier,
                "matched_attribute": resolution.matched_attribute,
            },
        )
    ]


def check_vendor_status(
    resolution: VendorResolutionResult | None,
    vendor: VendorEntity | None,
) -> list[VerificationFinding]:
    """Flag invoices from suspended or inactive vendors."""
    if (
        resolution is None
        or not resolution.resolved_vendor_id
        or resolution.status not in ("suspended", "inactive")
    ):
        return []

    status_str = resolution.status
    vendor_name = (
        resolution.legal_name
        or resolution.canonical_key
        or resolution.resolved_vendor_id
    )
    return [
        VerificationFinding(
            finding_type="suspended_vendor",
            severity="high",
            explanation=(
                f"Vendor '{vendor_name}' has status '{status_str}' in the "
                "vendor master registry and cannot be processed for payment."
            ),
            comparison_source="vendor_registry",
            deterministic_rule="vendor status in registry must be active",
            details={
                "vendor_id": resolution.resolved_vendor_id,
                "status": status_str,
            },
        )
    ]


def check_vendor_bank_account(
    resolution: VendorResolutionResult | None,
    invoice: InvoiceExtraction,
    vendor: VendorEntity | None,
) -> list[VerificationFinding]:
    """Flag invoices where remit-to coordinates do not match registered accounts."""
    if (
        resolution is None
        or not resolution.resolved_vendor_id
        or not invoice.vendor_bank_account
        or vendor is None
    ):
        return []

    clean_extracted = normalize_bank_account(invoice.vendor_bank_account)
    if not clean_extracted:
        return []

    matched = False
    for bank in vendor.bank_accounts:
        if normalize_bank_account(bank.account_number) == clean_extracted:
            matched = True
            break
        if bank.iban and normalize_bank_account(bank.iban) == clean_extracted:
            matched = True
            break

    if matched:
        return []

    return [
        VerificationFinding(
            finding_type="vendor_bank_account_mismatch",
            severity="high",
            explanation=(
                f"Remit-to bank account '{invoice.vendor_bank_account}' does not "
                f"match any approved bank account registered to vendor '{vendor.legal_name}'."
            ),
            comparison_source="vendor_registry",
            deterministic_rule="invoice remit-to coordinates must match registered vendor accounts",
            observed_value=invoice.vendor_bank_account,
            details={
                "extracted_bank_account": invoice.vendor_bank_account,
                "vendor_id": vendor.vendor_id,
                "approved_accounts_count": len(vendor.bank_accounts),
            },
        )
    ]


def check_vendor_tax_id(
    resolution: VendorResolutionResult | None,
    invoice: InvoiceExtraction,
    vendor: VendorEntity | None,
) -> list[VerificationFinding]:
    """Flag invoices where declared tax ID does not match registered tax records."""
    if (
        resolution is None
        or not resolution.resolved_vendor_id
        or not invoice.vendor_tax_id
        or vendor is None
    ):
        return []

    if not vendor.tax_ids:
        return []

    clean_extracted = normalize_tax_id(invoice.vendor_tax_id)
    if not clean_extracted:
        return []

    matched = any(
        normalize_tax_id(tax.tax_id) == clean_extracted for tax in vendor.tax_ids
    )
    if matched:
        return []

    return [
        VerificationFinding(
            finding_type="vendor_tax_id_mismatch",
            severity="high",
            explanation=(
                f"Declared tax ID '{invoice.vendor_tax_id}' does not match official "
                f"tax registration numbers on file for vendor '{vendor.legal_name}'."
            ),
            comparison_source="vendor_registry",
            deterministic_rule="invoice tax ID must match registered vendor tax numbers",
            observed_value=invoice.vendor_tax_id,
            details={
                "extracted_tax_id": invoice.vendor_tax_id,
                "vendor_id": vendor.vendor_id,
            },
        )
    ]
