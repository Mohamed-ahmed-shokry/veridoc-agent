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
    check_vendor_name,
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
                iban="GB74BARC20000012345678",
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
        vendor_bank_account="GB74 BARC 2000 0012 3456 78",
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


def test_check_vendor_name_mismatch_via_exact_tax_resolution(tmp_path: Path) -> None:
    repo = _setup_repository(tmp_path)
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Shell Consulting LLC",
        vendor_tax_id="GB123456789",
    )
    findings, resolution = check_vendor_registry(invoice, repo)
    assert resolution is not None
    assert resolution.resolved_vendor_id == "vnd_001"
    assert resolution.confidence == "exact_tax"

    name_findings = [f for f in findings if f.finding_type == "vendor_name_mismatch"]
    assert len(name_findings) == 1
    finding = name_findings[0]
    assert finding.severity == "medium"
    assert finding.comparison_source == "vendor_registry"
    assert finding.observed_value == "Shell Consulting LLC"
    assert finding.expected_value == "Acme Corporation Ltd"
    assert finding.details["vendor_id"] == "vnd_001"


def test_check_vendor_name_mismatch_via_exact_bank_resolution(tmp_path: Path) -> None:
    repo = _setup_repository(tmp_path)
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Unrelated Trading Co",
        vendor_bank_account="12345678",
    )
    findings, resolution = check_vendor_registry(invoice, repo)
    assert resolution is not None
    assert resolution.confidence == "exact_bank"
    assert [f.finding_type for f in findings] == ["vendor_name_mismatch"]


def test_check_vendor_name_accepts_registered_alias_and_reordered_tokens(
    tmp_path: Path,
) -> None:
    repo = _setup_repository(tmp_path)
    for matching_name in ("Acme Corp", "Corporation Acme Ltd"):
        invoice = InvoiceExtraction(
            document_type="invoice",
            vendor_name=matching_name,
            vendor_tax_id="GB123456789",
        )
        findings, _ = check_vendor_registry(invoice, repo)
        assert [f for f in findings if f.finding_type == "vendor_name_mismatch"] == []


def test_check_vendor_name_ignores_absent_or_unresolved(tmp_path: Path) -> None:
    repo = _setup_repository(tmp_path)
    for blank_name in (None, "   ", "---"):
        invoice = InvoiceExtraction(
            document_type="invoice",
            vendor_name=blank_name,
            vendor_tax_id="GB123456789",
        )
        findings, _ = check_vendor_registry(invoice, repo)
        assert [f for f in findings if f.finding_type == "vendor_name_mismatch"] == []

    assert (
        check_vendor_name(
            None,
            InvoiceExtraction(document_type="invoice", vendor_name="Any"),
            None,
        )
        == []
    )


def test_verification_service_routes_vendor_name_mismatch_to_review(
    tmp_path: Path,
) -> None:
    from veridoc.processing.verdict import derive_verdict

    repo = _setup_repository(tmp_path)
    service = VerificationService(repo)
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Shell Consulting LLC",
        vendor_tax_id="GB123456789",
    )
    snapshot = invoice.model_copy(deep=True)
    result = service.verify(invoice)
    assert invoice == snapshot
    assert any(f.finding_type == "vendor_name_mismatch" for f in result.findings)
    verdict = derive_verdict(result)
    assert verdict.status == "review_required"
