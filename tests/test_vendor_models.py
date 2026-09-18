"""Tests for Phase 12 vendor master domain models and extraction schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from veridoc.extraction.models import InvoiceExtraction
from veridoc.vendors.models import (
    VendorBankAccount,
    VendorEntity,
    VendorResolutionResult,
    VendorTaxId,
)
from veridoc.verification.models import VerificationFinding


def test_vendor_bank_account_valid() -> None:
    account = VendorBankAccount(
        account_number="12345678",
        bank_code="BARC",
        iban="GB82BARC20201512345678",
        routing_number="20-20-15",
    )
    assert account.account_number == "12345678"
    assert account.iban == "GB82BARC20201512345678"

    with pytest.raises(ValidationError):
        VendorBankAccount(account_number="", bank_code="BARC")

    with pytest.raises(ValidationError):
        VendorBankAccount(account_number="123", extra_field="forbidden")  # type: ignore[call-arg]


def test_vendor_tax_id_valid() -> None:
    tax = VendorTaxId(tax_id="GB123456789", country_code="GB")
    assert tax.tax_id == "GB123456789"
    assert tax.tax_type == "VAT"
    assert tax.country_code == "GB"

    with pytest.raises(ValidationError):
        VendorTaxId(tax_id="", tax_type="VAT")

    with pytest.raises(ValidationError):
        VendorTaxId(tax_id="123", unexpected="forbidden")  # type: ignore[call-arg]


def test_vendor_entity_valid() -> None:
    entity = VendorEntity(
        vendor_id="VEND-001",
        legal_name="Acme Corporation Ltd",
        canonical_key="acme-corporation",
        status="active",
        aliases=["Acme Corp", "Acme Logistics"],
        bank_accounts=[
            VendorBankAccount(account_number="12345678", iban="GB82BARC20201512345678")
        ],
        tax_ids=[VendorTaxId(tax_id="GB123456789", country_code="GB")],
    )
    assert entity.vendor_id == "VEND-001"
    assert entity.status == "active"
    assert len(entity.aliases) == 2
    assert len(entity.bank_accounts) == 1
    assert len(entity.tax_ids) == 1

    with pytest.raises(ValidationError):
        VendorEntity(
            vendor_id="VEND-001",
            legal_name="Acme Corp",
            canonical_key="acme-corp",
            status="invalid_status",  # type: ignore[arg-type]
        )


def test_vendor_resolution_result_valid() -> None:
    res = VendorResolutionResult(
        resolved_vendor_id="VEND-001",
        canonical_key="acme-corporation",
        legal_name="Acme Corporation Ltd",
        confidence="exact_tax",
        score=1.0,
        matched_attribute="tax_id:GB123456789",
        status="active",
    )
    assert res.confidence == "exact_tax"
    assert res.score == 1.0

    unresolved = VendorResolutionResult(
        confidence="unresolved",
        score=0.0,
    )
    assert unresolved.resolved_vendor_id is None
    assert unresolved.confidence == "unresolved"

    with pytest.raises(ValidationError):
        VendorResolutionResult(
            confidence="unresolved",
            score=1.5,  # score must be <= 1.0
        )


def test_invoice_extraction_backward_compatible() -> None:
    # Omitted vendor_tax_id and vendor_bank_account
    extraction = InvoiceExtraction(document_type="invoice", vendor_name="Acme Corp")
    assert extraction.vendor_name == "Acme Corp"
    assert extraction.vendor_tax_id is None
    assert extraction.vendor_bank_account is None

    # Provided vendor_tax_id and vendor_bank_account
    enriched = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Acme Corp",
        vendor_tax_id="GB123456789",
        vendor_bank_account="GB82BARC20201512345678",
    )
    assert enriched.vendor_tax_id == "GB123456789"
    assert enriched.vendor_bank_account == "GB82BARC20201512345678"


def test_verification_finding_vendor_registry() -> None:
    finding = VerificationFinding(
        finding_type="vendor_bank_account_mismatch",
        severity="high",
        explanation="Extracted remit-to account does not match vendor records.",
        comparison_source="vendor_registry",
        deterministic_rule="check_vendor_bank_account",
        observed_value="GB99UNKNOWN00000000",
        expected_value="GB82BARC20201512345678",
    )
    assert finding.finding_type == "vendor_bank_account_mismatch"
    assert finding.comparison_source == "vendor_registry"
    assert finding.severity == "high"
