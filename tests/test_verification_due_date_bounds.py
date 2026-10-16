"""Deterministic excessive credit window and due date bound verification tests."""

from datetime import date, timedelta
from decimal import Decimal

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.due_date_bounds import (
    MAXIMUM_CREDIT_WINDOW_DAYS,
    check_excessive_due_date_window,
)


def _invoice(**kwargs: object) -> InvoiceExtraction:
    """Build a minimal InvoiceExtraction with overridable keyword arguments."""
    defaults: dict[str, object] = {"document_type": "invoice"}
    defaults.update(kwargs)
    return InvoiceExtraction(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Cases that should NOT produce a finding (exclusion paths & valid windows)
# ---------------------------------------------------------------------------


def test_no_finding_when_dates_are_absent() -> None:
    assert check_excessive_due_date_window(_invoice()) == []
    assert check_excessive_due_date_window(_invoice(invoice_date=date(2026, 8, 1))) == []
    assert check_excessive_due_date_window(_invoice(due_date=date(2026, 8, 31))) == []


def test_no_finding_when_due_date_is_before_invoice_date() -> None:
    """Inverted dates are owned and reported by check_invoice_dates in arithmetic rules."""
    invoice = _invoice(
        invoice_date=date(2026, 9, 1),
        due_date=date(2026, 8, 1),
    )
    assert check_excessive_due_date_window(invoice) == []


def test_no_finding_when_due_date_equals_invoice_date() -> None:
    """Immediate payment / Net 0 has a credit window of 0 days."""
    invoice = _invoice(
        invoice_date=date(2026, 8, 1),
        due_date=date(2026, 8, 1),
    )
    assert check_excessive_due_date_window(invoice) == []


def test_no_finding_for_standard_commercial_terms() -> None:
    """Standard commercial credit terms (Net 15, 30, 60, 90, 120, 180) must pass cleanly."""
    base = date(2026, 1, 1)
    for days in (10, 15, 30, 45, 60, 90, 120, 180, 270, 360):
        invoice = _invoice(
            invoice_date=base,
            due_date=base + timedelta(days=days),
        )
        assert check_excessive_due_date_window(invoice) == []


def test_no_finding_at_exact_maximum_credit_window_boundary() -> None:
    """An invoice due exactly MAXIMUM_CREDIT_WINDOW_DAYS (365 days) after invoice_date is valid."""
    invoice_date = date(2026, 1, 1)
    due_date = invoice_date + timedelta(days=MAXIMUM_CREDIT_WINDOW_DAYS)
    invoice = _invoice(
        invoice_date=invoice_date,
        due_date=due_date,
    )
    assert check_excessive_due_date_window(invoice) == []


# ---------------------------------------------------------------------------
# Cases that SHOULD produce a finding (triggering paths)
# ---------------------------------------------------------------------------


def test_excessive_due_date_window_flags_one_day_past_maximum() -> None:
    """An invoice due 366 days after invoice_date triggers excessive_due_date_window."""
    invoice_date = date(2026, 1, 1)
    due_date = invoice_date + timedelta(days=MAXIMUM_CREDIT_WINDOW_DAYS + 1)
    invoice = _invoice(
        invoice_date=invoice_date,
        due_date=due_date,
    )

    findings = check_excessive_due_date_window(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "excessive_due_date_window"
    assert finding.severity == "medium"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == f"due_date - invoice_date <= {MAXIMUM_CREDIT_WINDOW_DAYS} days"
    assert finding.observed_value == due_date.isoformat()
    assert finding.expected_value == (invoice_date + timedelta(days=MAXIMUM_CREDIT_WINDOW_DAYS)).isoformat()
    assert finding.details == {
        "credit_window_days": 366,
        "max_allowed_days": MAXIMUM_CREDIT_WINDOW_DAYS,
        "invoice_date": invoice_date.isoformat(),
        "due_date": due_date.isoformat(),
    }


def test_excessive_due_date_window_flags_multi_year_ocr_hallucination() -> None:
    """Vision/OCR year errors (e.g. 2026 misread as 2036) are caught."""
    invoice = _invoice(
        invoice_date=date(2026, 5, 10),
        due_date=date(2036, 5, 10),
    )

    findings = check_excessive_due_date_window(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "excessive_due_date_window"
    assert finding.severity == "medium"
    assert finding.details["credit_window_days"] == (date(2036, 5, 10) - date(2026, 5, 10)).days
    assert "OCR year hallucination" in finding.explanation


def test_excessive_due_date_window_flags_two_year_window() -> None:
    """A two-year credit window is flagged."""
    invoice_date = date(2026, 1, 1)
    due_date = date(2028, 1, 1)
    invoice = _invoice(
        invoice_date=invoice_date,
        due_date=due_date,
    )

    findings = check_excessive_due_date_window(invoice)

    assert len(findings) == 1
    assert findings[0].finding_type == "excessive_due_date_window"
    assert findings[0].details["credit_window_days"] == 730


def test_check_excessive_due_date_window_preserves_invoice_immutability() -> None:
    """The pure check must never mutate invoice fields."""
    invoice_date = date(2026, 1, 1)
    due_date = date(2028, 1, 1)
    invoice = _invoice(
        invoice_date=invoice_date,
        due_date=due_date,
        total="1000.00",
        currency="USD",
    )
    copy_invoice = invoice.model_copy(deep=True)

    check_excessive_due_date_window(invoice)

    assert invoice == copy_invoice


class _FakeInvoiceRepository:
    """Minimal fake repository for VerificationService integration tests."""

    def list_vendor_invoices(self, vendor_key: str) -> list[object]:
        return []

    def get_purchase_order(self, vendor_key: str, po_number: str) -> object | None:
        return None


def test_verification_service_includes_excessive_due_date_window() -> None:
    """VerificationService.verify must execute check_excessive_due_date_window."""
    from veridoc.processing.verdict import derive_verdict
    from veridoc.verification.service import VerificationService

    invoice = _invoice(
        invoice_date=date(2026, 1, 1),
        due_date=date(2028, 1, 1),
        total="500.00",
        currency="USD",
    )
    service = VerificationService(repository=_FakeInvoiceRepository())  # type: ignore[arg-type]

    result = service.verify(invoice)

    types = [finding.finding_type for finding in result.findings]
    assert "excessive_due_date_window" in types

    verdict = derive_verdict(result)
    assert verdict.status == "review_required"
    assert verdict.highest_severity == "medium"
