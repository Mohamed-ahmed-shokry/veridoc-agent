"""Tests for deterministic multi-attribute vendor entity resolution."""

from pathlib import Path

from veridoc.extraction.models import InvoiceExtraction
from veridoc.persistence.sqlite import SQLiteVendorRepository
from veridoc.vendors.models import (
    VendorBankAccount,
    VendorEntity,
    VendorTaxId,
    derive_canonical_vendor_key,
)
from veridoc.vendors.resolution import (
    calculate_token_similarity,
    resolve_vendor,
    sorted_token_string,
)


def _make_extraction(
    vendor_name: str | None = None,
    vendor_identifier: str | None = None,
    vendor_tax_id: str | None = None,
    vendor_bank_account: str | None = None,
) -> InvoiceExtraction:
    return InvoiceExtraction(
        document_type="invoice",
        vendor_name=vendor_name,
        vendor_identifier=vendor_identifier,
        vendor_tax_id=vendor_tax_id,
        vendor_bank_account=vendor_bank_account,
    )


def _populate_test_vendors(repo: SQLiteVendorRepository) -> None:
    v1 = VendorEntity(
        vendor_id="vnd_001",
        legal_name="Acme Corporation Ltd",
        canonical_key=derive_canonical_vendor_key("Acme Corporation Ltd"),
        status="active",
        aliases=["Acme Corp", "Acme Supplies"],
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
    v2 = VendorEntity(
        vendor_id="vnd_002",
        legal_name="Beta Global Logistics Inc",
        canonical_key=derive_canonical_vendor_key("Beta Global Logistics Inc"),
        status="suspended",
        aliases=["Beta Freight", "Beta Global"],
        bank_accounts=[
            VendorBankAccount(
                account_number="87654321",
                bank_code="HSBC",
                iban="GB82HSBC20000087654321",
            )
        ],
        tax_ids=[
            VendorTaxId(tax_id="GB 987 6543 21", tax_type="VAT", country_code="GB")
        ],
    )
    repo.add_vendor(v1)
    repo.add_vendor(v2)


def test_sorted_token_string_and_similarity() -> None:
    assert sorted_token_string("Acme Corporation Ltd") == "acme corporation ltd"
    assert sorted_token_string("Ltd, Acme Corporation!") == "acme corporation ltd"

    assert (
        calculate_token_similarity("Acme Corporation Ltd", "Ltd Acme Corporation")
        == 1.0
    )
    assert calculate_token_similarity("", "Acme") == 0.0
    assert (
        calculate_token_similarity("Acme Corporation Ltd", "Acme Corporation Inc") > 0.8
    )


def test_resolve_vendor_exact_tax_id(tmp_path: Path) -> None:
    repo = SQLiteVendorRepository(tmp_path / "reference.sqlite")
    repo.initialize()
    _populate_test_vendors(repo)

    # Clean match with spaces removed
    invoice = _make_extraction(vendor_name="Unknown Name", vendor_tax_id="GB123456789")
    result = resolve_vendor(invoice, repo)
    assert result.confidence == "exact_tax"
    assert result.resolved_vendor_id == "vnd_001"
    assert result.canonical_key == "acme-corporation-ltd"
    assert result.legal_name == "Acme Corporation Ltd"
    assert result.score == 1.0
    assert result.status == "active"
    assert result.matched_attribute == "tax_id:GB123456789"


def test_resolve_vendor_exact_bank_account(tmp_path: Path) -> None:
    repo = SQLiteVendorRepository(tmp_path / "reference.sqlite")
    repo.initialize()
    _populate_test_vendors(repo)

    # Match by IBAN
    invoice = _make_extraction(
        vendor_name="Unknown Name",
        vendor_bank_account="GB82 BARC 2000 0012 3456 78",
    )
    result = resolve_vendor(invoice, repo)
    assert result.confidence == "exact_bank"
    assert result.resolved_vendor_id == "vnd_001"
    assert result.canonical_key == "acme-corporation-ltd"
    assert result.score == 1.0
    assert result.matched_attribute == "bank_account:GB82BARC20000012345678"


def test_resolve_vendor_exact_alias(tmp_path: Path) -> None:
    repo = SQLiteVendorRepository(tmp_path / "reference.sqlite")
    repo.initialize()
    _populate_test_vendors(repo)

    # Match by registered alias
    invoice = _make_extraction(vendor_name="Acme Supplies")
    result = resolve_vendor(invoice, repo)
    assert result.confidence == "exact_alias"
    assert result.resolved_vendor_id == "vnd_001"
    assert result.score == 1.0
    assert result.matched_attribute == "alias:acme-supplies"

    # Match by canonical key
    invoice2 = _make_extraction(vendor_name="Beta Global Logistics Inc")
    result2 = resolve_vendor(invoice2, repo)
    assert result2.confidence == "exact_alias"
    assert result2.resolved_vendor_id == "vnd_002"
    assert result2.status == "suspended"


def test_resolve_vendor_fuzzy_token_similarity(tmp_path: Path) -> None:
    repo = SQLiteVendorRepository(tmp_path / "reference.sqlite")
    repo.initialize()
    _populate_test_vendors(repo)

    # Inverted word order
    invoice = _make_extraction(vendor_name="Logistics Global Beta Inc")
    result = resolve_vendor(invoice, repo)
    assert result.confidence == "fuzzy_name"
    assert result.resolved_vendor_id == "vnd_002"
    assert result.score == 1.0


def test_resolve_vendor_unresolved_when_unknown(tmp_path: Path) -> None:
    repo = SQLiteVendorRepository(tmp_path / "reference.sqlite")
    repo.initialize()
    _populate_test_vendors(repo)

    invoice = _make_extraction(
        vendor_name="Completely Unknown Hardware Store",
        vendor_tax_id="US999999",
        vendor_bank_account="00000000",
    )
    result = resolve_vendor(invoice, repo)
    assert result.confidence == "unresolved"
    assert result.resolved_vendor_id is None
    assert result.score == 0.0


def test_resolve_vendor_empty_invoice(tmp_path: Path) -> None:
    repo = SQLiteVendorRepository(tmp_path / "reference.sqlite")
    repo.initialize()
    _populate_test_vendors(repo)

    invoice = _make_extraction()
    result = resolve_vendor(invoice, repo)
    assert result.confidence == "unresolved"
    assert result.resolved_vendor_id is None
