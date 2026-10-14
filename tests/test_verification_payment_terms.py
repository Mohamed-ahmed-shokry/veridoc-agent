"""Deterministic payment terms and due date consistency verification tests."""

from datetime import date

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.payment_terms import (
    check_payment_terms_due_date,
    parse_payment_terms_days,
)


def test_parse_payment_terms_days_handles_empty_and_none() -> None:
    assert parse_payment_terms_days(None) is None
    assert parse_payment_terms_days("") is None
    assert parse_payment_terms_days("   ") is None


def test_parse_payment_terms_days_parses_standard_net_terms() -> None:
    assert parse_payment_terms_days("Net 30") == 30
    assert parse_payment_terms_days("NET 30") == 30
    assert parse_payment_terms_days("net 15") == 15
    assert parse_payment_terms_days("Net 60") == 60
    assert parse_payment_terms_days("Net 90") == 90
    assert parse_payment_terms_days("Net 10") == 10
    assert parse_payment_terms_days("Net 45") == 45
    assert parse_payment_terms_days("Net 120") == 120
    assert parse_payment_terms_days("Net 30 days") == 30
    assert parse_payment_terms_days("30 days net") == 30
    assert parse_payment_terms_days("30 net") == 30
    assert parse_payment_terms_days("N/30") == 30
    assert parse_payment_terms_days("n/60") == 60


def test_parse_payment_terms_days_parses_cash_discount_terms() -> None:
    assert parse_payment_terms_days("2/10 Net 30") == 30
    assert parse_payment_terms_days("1/10, net 30") == 30
    assert parse_payment_terms_days("2% 10 Net 30") == 30
    assert parse_payment_terms_days("2/10 Net 60") == 60


def test_parse_payment_terms_days_parses_immediate_terms() -> None:
    assert parse_payment_terms_days("Due on receipt") == 0
    assert parse_payment_terms_days("due upon receipt") == 0
    assert parse_payment_terms_days("Immediate") == 0
    assert parse_payment_terms_days("Payment on receipt") == 0
    assert parse_payment_terms_days("Cash on delivery") == 0
    assert parse_payment_terms_days("COD") == 0
    assert parse_payment_terms_days("due immediately") == 0
    assert parse_payment_terms_days("Net 0") == 0


def test_parse_payment_terms_days_returns_none_for_unrecognized_terms() -> None:
    assert parse_payment_terms_days("See contract clause 4") is None
    assert parse_payment_terms_days("50% upfront, 50% on delivery") is None
    assert parse_payment_terms_days("Milestone billing") is None
    assert parse_payment_terms_days("arbitrary text") is None


def test_check_payment_terms_due_date_missing_fields_returns_empty() -> None:
    # Missing invoice_date
    assert (
        check_payment_terms_due_date(
            InvoiceExtraction(
                document_type="invoice",
                due_date="2026-08-31",
                payment_terms="Net 30",
            )
        )
        == []
    )

    # Missing due_date
    assert (
        check_payment_terms_due_date(
            InvoiceExtraction(
                document_type="invoice",
                invoice_date="2026-08-01",
                payment_terms="Net 30",
            )
        )
        == []
    )

    # Missing payment_terms
    assert (
        check_payment_terms_due_date(
            InvoiceExtraction(
                document_type="invoice",
                invoice_date="2026-08-01",
                due_date="2026-08-31",
            )
        )
        == []
    )

    # Unparseable payment_terms
    assert (
        check_payment_terms_due_date(
            InvoiceExtraction(
                document_type="invoice",
                invoice_date="2026-08-01",
                due_date="2026-08-31",
                payment_terms="Special agreement",
            )
        )
        == []
    )


def test_check_payment_terms_due_date_accepts_exact_match() -> None:
    # Net 30: 2026-08-01 + 30 days = 2026-08-31
    invoice_net30 = InvoiceExtraction(
        document_type="invoice",
        invoice_date="2026-08-01",
        due_date="2026-08-31",
        payment_terms="Net 30",
    )
    assert check_payment_terms_due_date(invoice_net30) == []

    # Net 15: 2026-08-01 + 15 days = 2026-08-16
    invoice_net15 = InvoiceExtraction(
        document_type="invoice",
        invoice_date="2026-08-01",
        due_date="2026-08-16",
        payment_terms="Net 15",
    )
    assert check_payment_terms_due_date(invoice_net15) == []

    # Due on receipt: 2026-08-01 + 0 days = 2026-08-01
    invoice_immediate = InvoiceExtraction(
        document_type="invoice",
        invoice_date="2026-08-01",
        due_date="2026-08-01",
        payment_terms="Due on receipt",
    )
    assert check_payment_terms_due_date(invoice_immediate) == []

    # Cash discount 2/10 Net 30
    invoice_discount = InvoiceExtraction(
        document_type="invoice",
        invoice_date="2026-08-01",
        due_date="2026-08-31",
        payment_terms="2/10 Net 30",
    )
    assert check_payment_terms_due_date(invoice_discount) == []


def test_check_payment_terms_due_date_accepts_weekend_business_day_rolls() -> None:
    # Saturday roll: 2026-10-01 (Thu) + 30 days = 2026-10-31 (Sat)
    # Rolled to 2026-11-02 (Mon, +2 days)
    assert date(2026, 10, 31).weekday() == 5  # Saturday
    assert date(2026, 11, 2).weekday() == 0  # Monday
    invoice_sat = InvoiceExtraction(
        document_type="invoice",
        invoice_date="2026-10-01",
        due_date="2026-11-02",
        payment_terms="Net 30",
    )
    assert check_payment_terms_due_date(invoice_sat) == []

    # Sunday roll: 2026-08-15 (Sat) + 15 days = 2026-08-30 (Sun)
    # Rolled to 2026-08-31 (Mon, +1 day)
    assert date(2026, 8, 30).weekday() == 6  # Sunday
    assert date(2026, 8, 31).weekday() == 0  # Monday
    invoice_sun = InvoiceExtraction(
        document_type="invoice",
        invoice_date="2026-08-15",
        due_date="2026-08-31",
        payment_terms="Net 15",
    )
    assert check_payment_terms_due_date(invoice_sun) == []


def test_check_payment_terms_due_date_flags_accelerated_due_date() -> None:
    # Net 30: 2026-08-01 + 30 days = expected 2026-08-31, but due_date is 2026-08-10 (21 days early)
    invoice = InvoiceExtraction(
        document_type="invoice",
        invoice_date="2026-08-01",
        due_date="2026-08-10",
        payment_terms="Net 30",
    )
    findings = check_payment_terms_due_date(invoice)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "payment_terms_due_date_mismatch"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_fields"
    assert (
        finding.deterministic_rule
        == "invoice.due_date == invoice.invoice_date + payment_terms_days"
    )
    assert finding.observed_value == "2026-08-10"
    assert finding.expected_value == "2026-08-31"
    assert (
        "21 days earlier than the 30-day payment terms specify" in finding.explanation
    )
    assert finding.details == {
        "payment_terms": "Net 30",
        "terms_days": 30,
        "expected_due_date": "2026-08-31",
        "observed_due_date": "2026-08-10",
        "discrepancy_days": -21,
        "is_accelerated": True,
    }


def test_check_payment_terms_due_date_flags_one_day_accelerated_due_date() -> None:
    # Net 30: 2026-08-01 + 30 days = expected 2026-08-31, but due_date is 2026-08-30 (1 day early)
    invoice = InvoiceExtraction(
        document_type="invoice",
        invoice_date="2026-08-01",
        due_date="2026-08-30",
        payment_terms="Net 30",
    )
    findings = check_payment_terms_due_date(invoice)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "high"
    assert "1 day earlier than the 30-day payment terms specify" in finding.explanation
    assert finding.details["discrepancy_days"] == -1
    assert finding.details["is_accelerated"] is True


def test_check_payment_terms_due_date_flags_accelerated_immediate_terms() -> None:
    # Due on receipt: invoice_date is 2026-08-10, but due_date is 2026-08-05 (earlier than invoice_date)
    invoice = InvoiceExtraction(
        document_type="invoice",
        invoice_date="2026-08-10",
        due_date="2026-08-05",
        payment_terms="Due on receipt",
    )
    findings = check_payment_terms_due_date(invoice)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "high"
    assert (
        "specifies immediate terms ('Due on receipt'), but due date"
        in finding.explanation
    )
    assert finding.details["is_accelerated"] is True


def test_check_payment_terms_due_date_flags_extended_due_date() -> None:
    # Net 30: 2026-08-01 + 30 days = expected 2026-08-31, but due_date is 2026-09-15 (15 days late)
    invoice = InvoiceExtraction(
        document_type="invoice",
        invoice_date="2026-08-01",
        due_date="2026-09-15",
        payment_terms="Net 30",
    )
    findings = check_payment_terms_due_date(invoice)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "payment_terms_due_date_mismatch"
    assert finding.severity == "medium"
    assert finding.comparison_source == "invoice_fields"
    assert (
        finding.deterministic_rule
        == "invoice.due_date == invoice.invoice_date + payment_terms_days"
    )
    assert finding.observed_value == "2026-09-15"
    assert finding.expected_value == "2026-08-31"
    assert "15 days later than the 30-day payment terms specify" in finding.explanation
    assert finding.details == {
        "payment_terms": "Net 30",
        "terms_days": 30,
        "expected_due_date": "2026-08-31",
        "observed_due_date": "2026-09-15",
        "discrepancy_days": 15,
        "is_accelerated": False,
    }


def test_check_payment_terms_due_date_flags_one_day_extended_due_date() -> None:
    # Net 30: 2026-08-01 + 30 days = expected 2026-08-31 (Monday), but due_date is 2026-09-01 (1 day late)
    assert date(2026, 8, 31).weekday() == 0  # Monday, so no weekend roll
    invoice = InvoiceExtraction(
        document_type="invoice",
        invoice_date="2026-08-01",
        due_date="2026-09-01",
        payment_terms="Net 30",
    )
    findings = check_payment_terms_due_date(invoice)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "medium"
    assert "1 day later than the 30-day payment terms specify" in finding.explanation
    assert finding.details["discrepancy_days"] == 1
    assert finding.details["is_accelerated"] is False


def test_check_payment_terms_due_date_flags_extended_immediate_terms() -> None:
    # Due on receipt: invoice_date is 2026-08-01, but due_date is 2026-08-31 (30 days late)
    invoice = InvoiceExtraction(
        document_type="invoice",
        invoice_date="2026-08-01",
        due_date="2026-08-31",
        payment_terms="Due on receipt",
    )
    findings = check_payment_terms_due_date(invoice)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "medium"
    assert (
        "specifies immediate payment ('Due on receipt'), but due date (2026-08-31) is 30 days after"
        in finding.explanation
    )
    assert finding.details["is_accelerated"] is False
