"""Deterministic required-field completeness verification tests."""

from datetime import date
from decimal import Decimal

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.completeness import (
    REQUIRED_INVOICE_FIELDS,
    check_required_fields,
)


def _invoice(**kwargs: object) -> InvoiceExtraction:
    """Build an InvoiceExtraction with default or overridden keyword arguments."""
    defaults: dict[str, object] = {"document_type": "invoice"}
    defaults.update(kwargs)
    return InvoiceExtraction(**defaults)  # type: ignore[arg-type]


def _complete_invoice(**kwargs: object) -> InvoiceExtraction:
    """Build a complete invoice that satisfies every required field."""
    defaults: dict[str, object] = {
        "document_type": "invoice",
        "vendor_name": "Acme Corp",
        "invoice_number": "INV-2026-001",
        "invoice_date": date(2026, 8, 1),
        "due_date": date(2026, 8, 31),
        "currency": "USD",
        "subtotal": Decimal("100.00"),
        "tax": Decimal("10.00"),
        "total": Decimal("110.00"),
    }
    defaults.update(kwargs)
    return InvoiceExtraction(**defaults)  # type: ignore[arg-type]


def test_required_invoice_fields_are_declared_in_fixed_order() -> None:
    """The required-field table is ordered and carries documented severities."""
    assert [(field.name, field.severity) for field in REQUIRED_INVOICE_FIELDS] == [
        ("invoice_number", "high"),
        ("invoice_date", "medium"),
        ("currency", "medium"),
        ("total", "high"),
    ]


def test_no_finding_when_all_required_fields_present() -> None:
    """A complete invoice returns no completeness findings."""
    assert check_required_fields(_complete_invoice()) == []


def test_missing_invoice_number_triggers_high_severity_finding() -> None:
    """Absent invoice_number produces one high-severity structured finding."""
    invoice = _complete_invoice(invoice_number=None)
    findings = check_required_fields(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "missing_required_field"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "invoice.invoice_number is not None"
    assert finding.observed_value is None
    assert finding.expected_value == "invoice_number"
    assert finding.details == {"field": "invoice_number"}
    assert "invoice_number" in finding.explanation


def test_missing_invoice_date_triggers_medium_severity_finding() -> None:
    """Absent invoice_date produces one medium-severity structured finding."""
    invoice = _complete_invoice(invoice_date=None)
    findings = check_required_fields(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "missing_required_field"
    assert finding.severity == "medium"
    assert finding.deterministic_rule == "invoice.invoice_date is not None"
    assert finding.expected_value == "invoice_date"
    assert finding.details == {"field": "invoice_date"}


def test_missing_currency_triggers_medium_severity_finding() -> None:
    """Absent currency produces one medium-severity structured finding."""
    invoice = _complete_invoice(currency=None)
    findings = check_required_fields(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "missing_required_field"
    assert finding.severity == "medium"
    assert finding.deterministic_rule == "invoice.currency is not None"
    assert finding.expected_value == "currency"
    assert finding.details == {"field": "currency"}


def test_missing_total_triggers_high_severity_finding() -> None:
    """Absent total produces one high-severity structured finding."""
    invoice = _complete_invoice(total=None)
    findings = check_required_fields(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "missing_required_field"
    assert finding.severity == "high"
    assert finding.deterministic_rule == "invoice.total is not None"
    assert finding.expected_value == "total"
    assert finding.details == {"field": "total"}


def test_multiple_missing_fields_preserve_declared_order() -> None:
    """Several absent fields produce findings in the declared table order."""
    invoice = _invoice(
        invoice_number="INV-2026-002",
        invoice_date=None,
        currency=None,
        total=None,
    )
    findings = check_required_fields(invoice)

    assert [finding.details["field"] for finding in findings] == [
        "invoice_date",
        "currency",
        "total",
    ]
    assert [finding.severity for finding in findings] == [
        "medium",
        "medium",
        "high",
    ]


def test_empty_invoice_yields_one_finding_per_required_field() -> None:
    """A completely empty invoice cannot pass completeness verification."""
    invoice = _invoice()
    findings = check_required_fields(invoice)

    assert len(findings) == len(REQUIRED_INVOICE_FIELDS)
    assert [finding.details["field"] for finding in findings] == [
        "invoice_number",
        "invoice_date",
        "currency",
        "total",
    ]
    assert all(finding.finding_type == "missing_required_field" for finding in findings)


def test_check_required_fields_preserves_input_immutability() -> None:
    """The completeness check does not mutate the input extraction."""
    invoice = _invoice()
    original_dump = invoice.model_dump()
    _ = check_required_fields(invoice)
    assert invoice.model_dump() == original_dump
