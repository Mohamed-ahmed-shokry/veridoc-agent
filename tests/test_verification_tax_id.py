"""Phase 36 vendor VAT identifier format verification tests (ADR 0042)."""

from __future__ import annotations

import pytest

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.tax_id import VAT_STRUCTURES, check_tax_id_format

VALID_VAT_NUMBERS = {
    "AT": "ATU12345678",
    "BE": "BE0123456789",
    "BG": "BG123456789",
    "CY": "CY12345678X",
    "CZ": "CZ12345678",
    "DE": "DE123456789",
    "DK": "DK12345678",
    "EE": "EE123456789",
    "EL": "EL123456789",
    "ES": "ESX1234567X",
    "FI": "FI12345678",
    "FR": "FRAB123456789",
    "GB": "GB123456789",
    "HR": "HR12345678901",
    "HU": "HU12345678",
    "IE": "IE1234567FA",
    "IT": "IT12345678901",
    "LT": "LT123456789",
    "LU": "LU12345678",
    "LV": "LV12345678901",
    "MT": "MT12345678",
    "NL": "NL123456789B01",
    "PL": "PL1234567890",
    "PT": "PT123456789",
    "RO": "RO12",
    "SE": "SE123456789012",
    "SI": "SI12345678",
    "SK": "SK1234567890",
    "XI": "XI123456789012",
}


def _invoice(tax_id: str | None) -> InvoiceExtraction:
    return InvoiceExtraction(document_type="invoice", vendor_tax_id=tax_id)


def test_valid_examples_cover_every_structure_prefix() -> None:
    assert set(VALID_VAT_NUMBERS) == set(VAT_STRUCTURES)


@pytest.mark.parametrize("tax_id", sorted(VALID_VAT_NUMBERS.values()))
def test_tax_id_format_accepts_valid_vat_numbers(tax_id: str) -> None:
    assert check_tax_id_format(_invoice(tax_id)) == []


@pytest.mark.parametrize(
    "tax_id",
    [
        "gb 123 4567 89",
        "DE 123.456.789",
        "nl-123456789-b01",
        "GB GD123",
        "GBHA123",
    ],
)
def test_tax_id_format_ignores_spacing_punctuation_and_case(tax_id: str) -> None:
    assert check_tax_id_format(_invoice(tax_id)) == []


@pytest.mark.parametrize("tax_id", [None, "", "   ", "\t\n"])
def test_tax_id_format_accepts_absent_and_blank(tax_id: str | None) -> None:
    assert check_tax_id_format(_invoice(tax_id)) == []


@pytest.mark.parametrize(
    "tax_id",
    ["US123456789", "12-3456789", "TAX-ID-PENDING", "ZZ123", "123456789"],
)
def test_tax_id_format_ignores_unrecognized_prefixes(tax_id: str) -> None:
    assert check_tax_id_format(_invoice(tax_id)) == []


@pytest.mark.parametrize(
    ("tax_id", "country"),
    [
        ("DE12345678", "DE"),
        ("DE1234567890", "DE"),
        ("DE12345678A", "DE"),
        ("GB1234567890", "GB"),
        ("GB1234567", "GB"),
        ("ATU1234567", "AT"),
        ("AT12345678", "AT"),
        ("NL123456789", "NL"),
        ("FR1234567890", "FR"),
        ("IT1234567890", "IT"),
        ("BE2123456789", "BE"),
    ],
)
def test_tax_id_format_flags_wrong_structure(tax_id: str, country: str) -> None:
    findings = check_tax_id_format(_invoice(tax_id))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "invalid_tax_id"
    assert finding.severity == "medium"
    assert finding.comparison_source == "invoice_fields"
    assert finding.observed_value == tax_id
    assert finding.details == {
        "field": "vendor_tax_id",
        "tax_id": tax_id,
        "country": country,
    }


def test_tax_id_format_reports_normalized_identifier() -> None:
    findings = check_tax_id_format(_invoice("de 1234-5678"))

    assert len(findings) == 1
    assert findings[0].details["tax_id"] == "DE12345678"


def test_tax_id_format_does_not_mutate_input() -> None:
    invoice = _invoice("DE 1234 5678")
    snapshot = invoice.model_dump()

    check_tax_id_format(invoice)

    assert invoice.model_dump() == snapshot


class _FakeInvoiceRepository:
    """Minimal repository fake for service integration tests."""

    def list_vendor_invoices(self, vendor_key: str) -> list[object]:
        return []

    def get_purchase_order(self, vendor_key: str, po_number: str) -> object | None:
        return None


def test_verification_service_reports_invalid_tax_id() -> None:
    from veridoc.processing.verdict import derive_verdict
    from veridoc.verification.service import VerificationService

    service = VerificationService(repository=_FakeInvoiceRepository())  # type: ignore[arg-type]

    result = service.verify(_invoice("DE12345678"))
    findings = [f for f in result.findings if f.finding_type == "invalid_tax_id"]

    assert len(findings) == 1
    assert findings[0].severity == "medium"
    verdict = derive_verdict(result)
    assert verdict.status == "review_required"


def test_verification_service_accepts_valid_tax_id() -> None:
    from veridoc.verification.service import VerificationService

    service = VerificationService(repository=_FakeInvoiceRepository())  # type: ignore[arg-type]

    result = service.verify(_invoice("DE123456789"))

    assert not [f for f in result.findings if f.finding_type == "invalid_tax_id"]
