"""Repository-backed verification tests."""

from datetime import date
from decimal import Decimal

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.references import HistoricalInvoice
from veridoc.verification.repository_checks import (
    check_duplicate_invoice_number,
    check_potential_duplicate_invoice,
)


def _history() -> list[HistoricalInvoice]:
    return [
        HistoricalInvoice(
            vendor_key="fictional-supplies",
            invoice_number="INV-001",
            invoice_date="2026-07-01",
        )
    ]


def test_duplicate_invoice_check_reports_a_matching_historical_invoice() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies",
        invoice_number="INV-001",
    )

    findings = check_duplicate_invoice_number(invoice, _history())

    assert len(findings) == 1
    assert findings[0].finding_type == "duplicate_invoice_number"
    assert findings[0].details == {
        "vendor_key": "fictional-supplies",
        "existing_invoice_number": "INV-001",
        "existing_invoice_date": "2026-07-01",
    }


def test_duplicate_invoice_check_matches_normalized_number_variants() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies",
        invoice_number="INV – 001",
    )

    findings = check_duplicate_invoice_number(invoice, _history())

    assert len(findings) == 1
    assert findings[0].finding_type == "duplicate_invoice_number"
    assert findings[0].observed_value == "INV – 001"
    assert findings[0].details["existing_invoice_number"] == "INV-001"


def test_duplicate_invoice_check_keeps_structural_differences_distinct() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies",
        invoice_number="INV001",
    )

    assert check_duplicate_invoice_number(invoice, _history()) == []


def test_duplicate_invoice_check_skips_absent_identifiers_and_unknown_invoices() -> (
    None
):
    assert (
        check_duplicate_invoice_number(
            InvoiceExtraction(
                document_type="invoice", vendor_name="Fictional Supplies"
            ),
            _history(),
        )
        == []
    )
    assert (
        check_duplicate_invoice_number(
            InvoiceExtraction(
                document_type="invoice",
                vendor_name="Fictional Supplies",
                invoice_number="INV-404",
            ),
            _history(),
        )
        == []
    )


def _priced_history() -> list[HistoricalInvoice]:
    return [
        HistoricalInvoice(
            vendor_key="fictional-supplies",
            invoice_number="INV-001",
            invoice_date=date(2026, 7, 1),
            currency="USD",
            total=Decimal("1250.00"),
        )
    ]


def test_potential_duplicate_flags_same_date_currency_total_with_different_number() -> (
    None
):
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies",
        invoice_number="INV-001-R",
        invoice_date=date(2026, 7, 1),
        currency="USD",
        total=Decimal("1250.00"),
    )

    findings = check_potential_duplicate_invoice(invoice, _priced_history())

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "potential_duplicate_invoice"
    assert finding.severity == "medium"
    assert finding.comparison_source == "invoice_register"
    assert finding.observed_value == "2026-07-01 | USD 1250.00"
    assert finding.details == {
        "vendor_key": "fictional-supplies",
        "invoice_date": "2026-07-01",
        "currency": "USD",
        "total": "1250.00",
        "observed_invoice_number": "INV-001-R",
        "existing_invoice_number": "INV-001",
    }


def test_potential_duplicate_flags_when_invoice_number_is_absent() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies",
        invoice_number=None,
        invoice_date=date(2026, 7, 1),
        currency="USD",
        total=Decimal("1250.00"),
    )

    findings = check_potential_duplicate_invoice(invoice, _priced_history())

    assert len(findings) == 1
    assert findings[0].finding_type == "potential_duplicate_invoice"
    assert findings[0].details["observed_invoice_number"] is None
    assert "different invoice number" not in findings[0].explanation


def test_potential_duplicate_skips_exact_and_normalized_same_invoice_number() -> None:
    exact = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies",
        invoice_number="INV-001",
        invoice_date=date(2026, 7, 1),
        currency="USD",
        total=Decimal("1250.00"),
    )
    normalized_variant = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies",
        invoice_number="inv – 001",
        invoice_date=date(2026, 7, 1),
        currency="USD",
        total=Decimal("1250.00"),
    )

    assert check_potential_duplicate_invoice(exact, _priced_history()) == []
    assert (
        check_potential_duplicate_invoice(normalized_variant, _priced_history()) == []
    )


def test_potential_duplicate_skips_missing_or_non_positive_fields() -> None:
    history = _priced_history()
    candidates = [
        InvoiceExtraction(
            document_type="invoice",
            invoice_number="INV-002",
            invoice_date=date(2026, 7, 1),
            currency="USD",
            total=Decimal("1250.00"),
        ),
        InvoiceExtraction(
            document_type="invoice",
            vendor_name="Fictional Supplies",
            invoice_number="INV-002",
            currency="USD",
            total=Decimal("1250.00"),
        ),
        InvoiceExtraction(
            document_type="invoice",
            vendor_name="Fictional Supplies",
            invoice_number="INV-002",
            invoice_date=date(2026, 7, 1),
            total=Decimal("1250.00"),
        ),
        InvoiceExtraction(
            document_type="invoice",
            vendor_name="Fictional Supplies",
            invoice_number="INV-002",
            invoice_date=date(2026, 7, 1),
            currency="USD",
        ),
        InvoiceExtraction(
            document_type="invoice",
            vendor_name="Fictional Supplies",
            invoice_number="INV-002",
            invoice_date=date(2026, 7, 1),
            currency="USD",
            total=Decimal("0.00"),
        ),
        InvoiceExtraction(
            document_type="invoice",
            vendor_name="Fictional Supplies",
            invoice_number="INV-002",
            invoice_date=date(2026, 7, 1),
            currency="USD",
            total=Decimal("-50.00"),
        ),
    ]

    for candidate in candidates:
        assert check_potential_duplicate_invoice(candidate, history) == []


def test_potential_duplicate_skips_distinct_date_currency_total_and_incomplete_history() -> (
    None
):
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies",
        invoice_number="INV-002",
        invoice_date=date(2026, 7, 1),
        currency="USD",
        total=Decimal("1250.00"),
    )
    history = [
        HistoricalInvoice(
            vendor_key="fictional-supplies",
            invoice_number="INV-001",
            invoice_date=date(2026, 7, 2),
            currency="USD",
            total=Decimal("1250.00"),
        ),
        HistoricalInvoice(
            vendor_key="fictional-supplies",
            invoice_number="INV-003",
            invoice_date=date(2026, 7, 1),
            currency="EUR",
            total=Decimal("1250.00"),
        ),
        HistoricalInvoice(
            vendor_key="fictional-supplies",
            invoice_number="INV-004",
            invoice_date=date(2026, 7, 1),
            currency="USD",
            total=Decimal("1250.01"),
        ),
        HistoricalInvoice(
            vendor_key="fictional-supplies",
            invoice_number="INV-005",
            invoice_date=date(2026, 7, 1),
            currency=None,
            total=Decimal("1250.00"),
        ),
        HistoricalInvoice(
            vendor_key="fictional-supplies",
            invoice_number="INV-006",
            invoice_date=date(2026, 7, 1),
            currency="USD",
            total=None,
        ),
    ]

    assert check_potential_duplicate_invoice(invoice, history) == []


def test_potential_duplicate_preserves_input_immutability() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies",
        invoice_number="INV-002",
        invoice_date=date(2026, 7, 1),
        currency="USD",
        total=Decimal("1250.00"),
    )
    history = _priced_history()
    invoice_before = invoice.model_dump()
    history_before = [item.model_dump() for item in history]

    findings = check_potential_duplicate_invoice(invoice, history)

    assert len(findings) == 1
    assert invoice.model_dump() == invoice_before
    assert [item.model_dump() for item in history] == history_before


def test_verification_service_routes_potential_duplicate_to_review_required(
    tmp_path,
) -> None:
    from veridoc.persistence.sqlite import SQLiteInvoiceRepository
    from veridoc.processing.verdict import derive_verdict
    from veridoc.verification.service import VerificationService

    repository = SQLiteInvoiceRepository(tmp_path / "reference.db")
    repository.initialize()
    repository.add_invoice(
        HistoricalInvoice(
            vendor_key="fictional-supplies",
            invoice_number="INV-001",
            invoice_date=date(2026, 7, 1),
            currency="USD",
            total=Decimal("1250.00"),
        )
    )
    service = VerificationService(repository=repository)

    resubmitted = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies",
        invoice_number="INV-001-A",
        invoice_date=date(2026, 7, 1),
        currency="USD",
        total=Decimal("1250.00"),
    )
    result = service.verify(resubmitted, reference_date=date(2026, 7, 5))
    finding_types = [finding.finding_type for finding in result.findings]
    assert "potential_duplicate_invoice" in finding_types
    assert "duplicate_invoice_number" not in finding_types
    assert derive_verdict(result).status == "review_required"

    exact_duplicate = resubmitted.model_copy(update={"invoice_number": "INV-001"})
    exact_result = service.verify(exact_duplicate, reference_date=date(2026, 7, 5))
    exact_types = [finding.finding_type for finding in exact_result.findings]
    assert "duplicate_invoice_number" in exact_types
    assert "potential_duplicate_invoice" not in exact_types
