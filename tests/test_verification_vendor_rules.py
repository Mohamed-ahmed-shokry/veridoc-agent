"""Tests for deterministic vendor registry and bank reconciliation rules."""

from pathlib import Path

from veridoc.extraction.models import InvoiceExtraction
from veridoc.persistence.sqlite import SQLiteInvoiceRepository
from veridoc.vendors.models import (
    VendorBankAccount,
    VendorEntity,
    VendorTaxId,
    derive_canonical_vendor_key,
)
from veridoc.verification.service import VerificationService
from veridoc.verification.vendor_rules import (
    check_vendor_registration,
    check_vendor_registry,
)


def _setup_repository(tmp_path: Path) -> SQLiteInvoiceRepository:
    repo = SQLiteInvoiceRepository(tmp_path / "reference.sqlite")
    repo.initialize()

    active_vendor = VendorEntity(
        vendor_id="vnd_001",
        legal_name="Acme Corporation Ltd",
        canonical_key=derive_canonical_vendor_key("Acme Corporation Ltd"),
        status="active",
        aliases=["Acme Corp"],
        bank_accounts=[
            VendorBankAccount(
                account_number="12345678",
                bank_code="BARC",
                iban="GB82BARC20000012345678",
            )
        ],
        tax_ids=[
            VendorTaxId(tax_id="GB 123 4567 89", tax_type="VAT", country_code="GB")
        ],
    )
    suspended_vendor = VendorEntity(
        vendor_id="vnd_002",
        legal_name="Blocked Supplier Inc",
        canonical_key=derive_canonical_vendor_key("Blocked Supplier Inc"),
        status="suspended",
        aliases=[],
        bank_accounts=[
            VendorBankAccount(account_number="99999999", iban="GB82HSBC99999999")
        ],
        tax_ids=[VendorTaxId(tax_id="GB999999999", tax_type="VAT")],
    )
    repo.add_vendor(active_vendor)
    repo.add_vendor(suspended_vendor)
    return repo


def test_check_vendor_registration_flags_unknown_vendor(tmp_path: Path) -> None:
    repo = _setup_repository(tmp_path)
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Unknown Unregistered Supplier Ltd",
    )
    findings, resolution = check_vendor_registry(invoice, repo)
    assert resolution is not None
    assert resolution.confidence == "unresolved"

    reg_findings = [f for f in findings if f.finding_type == "unregistered_vendor"]
    assert len(reg_findings) == 1
    assert reg_findings[0].severity == "medium"
    assert reg_findings[0].comparison_source == "vendor_registry"
    assert "Unknown Unregistered Supplier Ltd" in reg_findings[0].explanation


def test_check_vendor_registration_silent_on_no_vendor_data() -> None:
    invoice = InvoiceExtraction(document_type="invoice")
    findings = check_vendor_registration(
        resolution=None,
        invoice=invoice,
    )
    assert findings == []

    # With confidence unresolved and no vendor data
    from veridoc.vendors.models import VendorResolutionResult

    res = VendorResolutionResult(confidence="unresolved", score=0.0)
    assert check_vendor_registration(res, invoice) == []


def test_check_vendor_status_flags_suspended_vendor(tmp_path: Path) -> None:
    repo = _setup_repository(tmp_path)
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Blocked Supplier Inc",
    )
    findings, resolution = check_vendor_registry(invoice, repo)
    assert resolution is not None
    assert resolution.resolved_vendor_id == "vnd_002"

    suspended_findings = [f for f in findings if f.finding_type == "suspended_vendor"]
    assert len(suspended_findings) == 1
    assert suspended_findings[0].severity == "high"
    assert "suspended" in suspended_findings[0].explanation


def test_check_vendor_bank_account_mismatch_flags_spoofed_account(
    tmp_path: Path,
) -> None:
    repo = _setup_repository(tmp_path)
    # Correct vendor name, but fraudulent remit-to account
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Acme Corporation Ltd",
        vendor_bank_account="99887766",  # Attacker's redirected bank account
    )
    findings, resolution = check_vendor_registry(invoice, repo)
    assert resolution is not None
    assert resolution.resolved_vendor_id == "vnd_001"

    bank_findings = [
        f for f in findings if f.finding_type == "vendor_bank_account_mismatch"
    ]
    assert len(bank_findings) == 1
    assert bank_findings[0].severity == "high"
    assert "99887766" in bank_findings[0].explanation
    assert bank_findings[0].observed_value == "99887766"


def test_check_vendor_bank_account_matches_verified_iban(tmp_path: Path) -> None:
    repo = _setup_repository(tmp_path)
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Acme Corporation Ltd",
        vendor_bank_account="GB82 BARC 2000 0012 3456 78",
    )
    findings, resolution = check_vendor_registry(invoice, repo)
    assert resolution is not None
    assert resolution.resolved_vendor_id == "vnd_001"

    bank_findings = [
        f for f in findings if f.finding_type == "vendor_bank_account_mismatch"
    ]
    assert len(bank_findings) == 0


def test_check_vendor_tax_id_mismatch(tmp_path: Path) -> None:
    repo = _setup_repository(tmp_path)
    # Correct vendor name, but wrong tax ID declared on invoice
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Acme Corporation Ltd",
        vendor_tax_id="GB 999 0000 11",
    )
    findings, resolution = check_vendor_registry(invoice, repo)
    assert resolution is not None
    assert resolution.resolved_vendor_id == "vnd_001"

    tax_findings = [f for f in findings if f.finding_type == "vendor_tax_id_mismatch"]
    assert len(tax_findings) == 1
    assert tax_findings[0].severity == "high"
    assert "GB 999 0000 11" in tax_findings[0].explanation


def test_verification_service_integrates_vendor_rules(tmp_path: Path) -> None:
    repo = _setup_repository(tmp_path)
    service = VerificationService(repo)

    # Legitimate invoice matching all master data
    valid_invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Acme Corporation Ltd",
        vendor_bank_account="12345678",
        vendor_tax_id="GB123456789",
    )
    result = service.verify(valid_invoice)
    assert result.vendor_resolution is not None
    assert result.vendor_resolution.resolved_vendor_id == "vnd_001"
    vendor_findings = [
        f for f in result.findings if f.comparison_source == "vendor_registry"
    ]
    assert len(vendor_findings) == 0

    # Invoice with redirected bank account (fraud scenario)
    fraud_invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Acme Corporation Ltd",
        vendor_bank_account="FRAUD_ACCOUNT_999",
        vendor_tax_id="GB123456789",
    )
    fraud_result = service.verify(fraud_invoice)
    assert any(
        f.finding_type == "vendor_bank_account_mismatch" for f in fraud_result.findings
    )
