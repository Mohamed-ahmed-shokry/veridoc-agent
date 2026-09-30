"""Deterministic stale invoice detection tests.

The staleness check fires when all three conditions are met:
- invoice_date is present and more than STALENESS_THRESHOLD_DAYS before today;
- purchase_order_number is absent or blank;
- total is present and greater than zero.

All tests inject an explicit reference_date so results are independent of
the wall clock.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.staleness import (
    STALENESS_THRESHOLD_DAYS,
    check_invoice_staleness,
)


def _invoice(**kwargs: object) -> InvoiceExtraction:
    """Build a minimal InvoiceExtraction with overridable keyword arguments."""
    defaults: dict[str, object] = {"document_type": "invoice"}
    defaults.update(kwargs)
    return InvoiceExtraction(**defaults)  # type: ignore[arg-type]


TODAY = date(2026, 9, 30)
STALE_DATE = TODAY - timedelta(days=STALENESS_THRESHOLD_DAYS + 1)
FRESH_DATE = TODAY - timedelta(days=STALENESS_THRESHOLD_DAYS - 1)
THRESHOLD_DATE_EXACT = TODAY - timedelta(days=STALENESS_THRESHOLD_DAYS)


# ---------------------------------------------------------------------------
# Cases that should NOT produce a finding
# ---------------------------------------------------------------------------


def test_no_finding_when_invoice_date_is_absent() -> None:
    invoice = _invoice(total="500.00")
    assert check_invoice_staleness(invoice, reference_date=TODAY) == []


def test_no_finding_when_total_is_absent() -> None:
    invoice = _invoice(invoice_date=STALE_DATE)
    assert check_invoice_staleness(invoice, reference_date=TODAY) == []


def test_no_finding_when_total_is_zero() -> None:
    invoice = _invoice(invoice_date=STALE_DATE, total="0.00")
    assert check_invoice_staleness(invoice, reference_date=TODAY) == []


def test_no_finding_when_total_is_negative() -> None:
    """A negative total is a credit note or data artifact; not a payment risk."""
    invoice = _invoice(invoice_date=STALE_DATE, total="-100.00")
    assert check_invoice_staleness(invoice, reference_date=TODAY) == []


def test_no_finding_when_date_is_exactly_at_threshold() -> None:
    """Invoice date equal to threshold_date is not strictly before it."""
    invoice = _invoice(invoice_date=THRESHOLD_DATE_EXACT, total="500.00")
    assert check_invoice_staleness(invoice, reference_date=TODAY) == []


def test_no_finding_when_date_is_fresh() -> None:
    invoice = _invoice(invoice_date=FRESH_DATE, total="500.00")
    assert check_invoice_staleness(invoice, reference_date=TODAY) == []


def test_no_finding_when_purchase_order_number_is_present() -> None:
    """PO-anchored invoices are excluded; the PO ceiling rule covers them."""
    invoice = _invoice(
        invoice_date=STALE_DATE,
        total="500.00",
        purchase_order_number="PO-2025-001",
    )
    assert check_invoice_staleness(invoice, reference_date=TODAY) == []


def test_no_finding_when_purchase_order_number_is_whitespace() -> None:
    """A whitespace-only PO number is treated the same as absent."""
    # Whitespace-only: the rule checks .strip(), so this should NOT suppress.
    # We verify the boundary: "   " is blank and should not suppress the check.
    invoice = _invoice(
        invoice_date=STALE_DATE,
        total="500.00",
        purchase_order_number="   ",
    )
    findings = check_invoice_staleness(invoice, reference_date=TODAY)
    # A whitespace-only PO number is treated as absent → finding fires.
    assert len(findings) == 1
    assert findings[0].finding_type == "stale_invoice"


# ---------------------------------------------------------------------------
# Cases that SHOULD produce a finding
# ---------------------------------------------------------------------------


def test_stale_invoice_produces_finding_when_all_conditions_met() -> None:
    invoice = _invoice(invoice_date=STALE_DATE, total="1500.00")
    findings = check_invoice_staleness(invoice, reference_date=TODAY)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "stale_invoice"
    assert finding.severity == "medium"
    assert finding.comparison_source == "invoice_fields"
    assert finding.observed_value == STALE_DATE.isoformat()
    assert finding.expected_value == THRESHOLD_DATE_EXACT.isoformat()


def test_stale_finding_records_days_old_in_details() -> None:
    stale_date = TODAY - timedelta(days=150)
    invoice = _invoice(invoice_date=stale_date, total="200.00")
    findings = check_invoice_staleness(invoice, reference_date=TODAY)

    assert findings[0].details["days_old"] == 150
    assert findings[0].details["threshold_days"] == STALENESS_THRESHOLD_DAYS
    assert findings[0].details["reference_date"] == TODAY.isoformat()


def test_stale_finding_includes_threshold_in_deterministic_rule() -> None:
    invoice = _invoice(invoice_date=STALE_DATE, total="100.00")
    findings = check_invoice_staleness(invoice, reference_date=TODAY)

    rule = findings[0].deterministic_rule
    assert str(STALENESS_THRESHOLD_DAYS) in rule
    assert "purchase_order_number" in rule


def test_stale_invoice_one_day_past_threshold() -> None:
    """One day past the boundary is the minimal stale case."""
    stale_by_one = TODAY - timedelta(days=STALENESS_THRESHOLD_DAYS + 1)
    invoice = _invoice(invoice_date=stale_by_one, total="0.01")
    findings = check_invoice_staleness(invoice, reference_date=TODAY)

    assert len(findings) == 1
    assert findings[0].finding_type == "stale_invoice"


def test_stale_invoice_very_old_date() -> None:
    """An invoice from years ago still produces exactly one finding."""
    ancient = date(2020, 1, 1)
    invoice = _invoice(invoice_date=ancient, total="999.99")
    findings = check_invoice_staleness(invoice, reference_date=TODAY)

    assert len(findings) == 1
    assert findings[0].details["days_old"] == (TODAY - ancient).days


def test_stale_invoice_with_minimal_positive_total() -> None:
    """Any positive total qualifies, including the smallest representable amount."""
    invoice = _invoice(invoice_date=STALE_DATE, total="0.000001")
    findings = check_invoice_staleness(invoice, reference_date=TODAY)

    assert len(findings) == 1


def test_default_reference_date_is_today() -> None:
    """When no reference_date is supplied the rule uses date.today()."""
    fresh_relative_to_today = date.today() - timedelta(days=1)
    invoice = _invoice(invoice_date=fresh_relative_to_today, total="100.00")
    # Fresh relative to today → no finding.
    assert check_invoice_staleness(invoice) == []


@pytest.mark.parametrize(
    "po_number",
    ["PO-001", "po 001", "0000001", "  PO  "],
)
def test_non_empty_purchase_order_suppresses_finding(po_number: str) -> None:
    """Any non-blank PO number suppresses the stale invoice finding."""
    invoice = _invoice(
        invoice_date=STALE_DATE,
        total="500.00",
        purchase_order_number=po_number,
    )
    assert check_invoice_staleness(invoice, reference_date=TODAY) == []


def test_stale_check_does_not_mutate_invoice() -> None:
    """The pure function must not alter any field on the invoice."""
    invoice = _invoice(invoice_date=STALE_DATE, total="300.00")
    original_date = invoice.invoice_date
    original_total = invoice.total

    check_invoice_staleness(invoice, reference_date=TODAY)

    assert invoice.invoice_date == original_date
    assert invoice.total == original_total


def test_stale_total_uses_decimal_comparison() -> None:
    """total must be compared as Decimal, not as a floating-point approximation."""
    # 0.1 in IEEE 754 binary floating point is not exactly 0.1, but
    # Pydantic stores it as Decimal("0.1"), which compares correctly.
    invoice = _invoice(invoice_date=STALE_DATE, total="0.1")
    findings = check_invoice_staleness(invoice, reference_date=TODAY)

    assert len(findings) == 1
    assert invoice.total == Decimal("0.1")
