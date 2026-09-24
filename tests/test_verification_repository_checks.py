"""Repository-backed verification tests."""

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.references import HistoricalInvoice
from veridoc.verification.repository_checks import check_duplicate_invoice_number


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
