"""Deterministic future invoice date detection tests.

The future invoice date check fires whenever invoice_date is present and
strictly after the reference processing date (today). It flags post-dated
invoices to prevent premature trust, accounting period cutoff manipulation,
fraudulent advance disbursement, and OCR/vision date extraction errors.

All tests inject an explicit reference_date so results are strictly
deterministic and independent of the wall clock.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from veridoc.extraction.models import InvoiceExtraction, InvoiceLineItem
from veridoc.processing.verdict import derive_verdict
from veridoc.verification.future_dates import check_future_invoice_date
from veridoc.verification.references import HistoricalInvoice
from veridoc.verification.service import VerificationService


def _invoice(**kwargs: object) -> InvoiceExtraction:
    """Build a minimal InvoiceExtraction with overridable keyword arguments."""
    defaults: dict[str, object] = {"document_type": "invoice"}
    defaults.update(kwargs)
    return InvoiceExtraction(**defaults)  # type: ignore[arg-type]


TODAY = date(2026, 10, 4)
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)
FUTURE_DATE = TODAY + timedelta(days=45)
FAR_FUTURE_DATE = date(2035, 1, 1)
PAST_DATE = date(2026, 8, 1)


# ---------------------------------------------------------------------------
# Cases that should NOT produce a finding
# ---------------------------------------------------------------------------


def test_no_finding_when_invoice_date_is_absent() -> None:
    invoice = _invoice(total="500.00")
    assert check_future_invoice_date(invoice, reference_date=TODAY) == []


def test_no_finding_when_invoice_date_is_today() -> None:
    """Invoice date equal to today is current, not in the future."""
    invoice = _invoice(invoice_date=TODAY, total="500.00")
    assert check_future_invoice_date(invoice, reference_date=TODAY) == []


def test_no_finding_when_invoice_date_is_yesterday() -> None:
    invoice = _invoice(invoice_date=YESTERDAY, total="500.00")
    assert check_future_invoice_date(invoice, reference_date=TODAY) == []


def test_no_finding_when_invoice_date_is_past() -> None:
    invoice = _invoice(invoice_date=PAST_DATE, total="500.00")
    assert check_future_invoice_date(invoice, reference_date=TODAY) == []


# ---------------------------------------------------------------------------
# Cases that SHOULD produce a finding
# ---------------------------------------------------------------------------


def test_finding_produced_when_invoice_date_is_tomorrow() -> None:
    """One day in the future is the minimal post-dated case."""
    invoice = _invoice(invoice_date=TOMORROW, total="100.00")
    findings = check_future_invoice_date(invoice, reference_date=TODAY)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "future_invoice_date"
    assert finding.severity == "medium"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "invoice_date <= today"
    assert finding.observed_value == TOMORROW.isoformat()
    assert finding.expected_value == TODAY.isoformat()
    assert finding.details == {
        "days_in_future": 1,
        "reference_date": TODAY.isoformat(),
    }


def test_finding_produced_when_invoice_date_is_far_future() -> None:
    invoice = _invoice(invoice_date=FAR_FUTURE_DATE, total="1200.00")
    findings = check_future_invoice_date(invoice, reference_date=TODAY)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "future_invoice_date"
    assert finding.severity == "medium"
    expected_days = (FAR_FUTURE_DATE - TODAY).days
    assert finding.details["days_in_future"] == expected_days


def test_explanation_singular_day_formatting() -> None:
    invoice = _invoice(invoice_date=TOMORROW)
    findings = check_future_invoice_date(invoice, reference_date=TODAY)

    assert len(findings) == 1
    assert "1 day in the future" in findings[0].explanation


def test_explanation_plural_days_formatting() -> None:
    invoice = _invoice(invoice_date=FUTURE_DATE)
    findings = check_future_invoice_date(invoice, reference_date=TODAY)

    assert len(findings) == 1
    assert "45 days in the future" in findings[0].explanation


# ---------------------------------------------------------------------------
# Independent conditions (PO presence and totals do NOT suppress)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "po_number",
    ["PO-12345", "po 99", "STANDARD-CONTRACT-PO", "  PO  "],
)
def test_purchase_order_does_not_suppress_future_date_finding(po_number: str) -> None:
    """A PO authorizes spending but never authorizes post-dated invoices."""
    invoice = _invoice(
        invoice_date=TOMORROW,
        purchase_order_number=po_number,
        total="500.00",
    )
    findings = check_future_invoice_date(invoice, reference_date=TODAY)
    assert len(findings) == 1
    assert findings[0].finding_type == "future_invoice_date"


def test_zero_total_does_not_suppress_future_date_finding() -> None:
    """Zero-total invoices dated in the future cannot be legally booked."""
    invoice = _invoice(invoice_date=TOMORROW, total="0.00")
    findings = check_future_invoice_date(invoice, reference_date=TODAY)
    assert len(findings) == 1
    assert findings[0].finding_type == "future_invoice_date"


def test_negative_total_credit_note_does_not_suppress_future_date_finding() -> None:
    """Credit notes dated in the future cannot be recognized before the date."""
    invoice = _invoice(invoice_date=TOMORROW, total="-250.00")
    findings = check_future_invoice_date(invoice, reference_date=TODAY)
    assert len(findings) == 1
    assert findings[0].finding_type == "future_invoice_date"


def test_absent_total_does_not_suppress_future_date_finding() -> None:
    """An invoice missing its total is still post-dated if invoice_date is future."""
    invoice = _invoice(invoice_date=TOMORROW, total=None)
    findings = check_future_invoice_date(invoice, reference_date=TODAY)
    assert len(findings) == 1
    assert findings[0].finding_type == "future_invoice_date"


def test_future_date_check_does_not_mutate_invoice() -> None:
    """The pure check function must never mutate its input."""
    invoice = _invoice(invoice_date=TOMORROW, total="500.00")
    original_date = invoice.invoice_date
    original_total = invoice.total

    check_future_invoice_date(invoice, reference_date=TODAY)

    assert invoice.invoice_date == original_date
    assert invoice.total == original_total


def test_default_reference_date_is_utc_today() -> None:
    """When reference_date is None, the function uses datetime.now(UTC).date()."""
    today_utc = datetime.now(UTC).date()
    yesterday = today_utc - timedelta(days=1)
    tomorrow = today_utc + timedelta(days=1)

    past_invoice = _invoice(invoice_date=yesterday)
    assert check_future_invoice_date(past_invoice) == []

    future_invoice = _invoice(invoice_date=tomorrow)
    findings = check_future_invoice_date(future_invoice)
    assert len(findings) == 1
    assert findings[0].finding_type == "future_invoice_date"


# ---------------------------------------------------------------------------
# Integration with VerificationService and Processing Verdict
# ---------------------------------------------------------------------------


class _StubRepository:
    def list_vendor_invoices(self, vendor_key: str) -> list[HistoricalInvoice]:
        return []

    def get_purchase_order(self, vendor_key: str, purchase_order_number: str) -> None:
        return None


def test_verification_service_includes_future_date_finding() -> None:
    service = VerificationService(_StubRepository())
    invoice = _invoice(
        vendor_name="Acme Corp",
        invoice_number="INV-2026-999",
        invoice_date=TOMORROW,
        total="500.00",
        currency="USD",
        line_items=[
            InvoiceLineItem(
                product_identifier="ITEM-1",
                quantity=Decimal(1),
                unit_price=Decimal("500.00"),
                total_price=Decimal("500.00"),
            )
        ],
    )

    result = service.verify(invoice, reference_date=TODAY)
    finding_types = [f.finding_type for f in result.findings]

    assert "future_invoice_date" in finding_types


def test_processing_verdict_derivation_marks_review_required() -> None:
    service = VerificationService(_StubRepository())
    invoice = _invoice(
        vendor_name="Acme Corp",
        invoice_number="INV-2026-999",
        invoice_date=TOMORROW,
        total="500.00",
        currency="USD",
        line_items=[
            InvoiceLineItem(
                product_identifier="ITEM-1",
                quantity=Decimal(1),
                unit_price=Decimal("500.00"),
                total_price=Decimal("500.00"),
            )
        ],
    )

    verification_result = service.verify(invoice, reference_date=TODAY)
    verdict = derive_verdict(verification_result)

    assert verdict.status == "review_required"
    assert verdict.highest_severity in ("medium", "high")
    assert verdict.finding_count >= 1
