"""Tests for deterministic purchase order number syntax, length, and placeholder verification."""

from __future__ import annotations

import copy

import pytest

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.purchase_order_number import (
    MAX_PURCHASE_ORDER_NUMBER_LENGTH,
    check_purchase_order_number_format,
    is_valid_purchase_order_number,
)


def _invoice(po_number: str | None) -> InvoiceExtraction:
    return InvoiceExtraction(
        document_type="invoice",
        purchase_order_number=po_number,
    )


@pytest.mark.parametrize(
    "valid_number",
    [
        "PO-2026-001",
        "4500012345",
        "PO/99124",
        "ENG-PO-882",
        "123456",
        "ORD-99882",
        "PO.2026.01",
        "PO-A102-B",
        "REQ-88712-X",
        "CONTRACT-2026",
    ],
)
def test_check_purchase_order_number_passes_on_valid_numbers(
    valid_number: str,
) -> None:
    assert check_purchase_order_number_format(_invoice(valid_number)) == []
    assert is_valid_purchase_order_number(valid_number) is True


def test_check_purchase_order_number_passes_on_absent_number() -> None:
    assert check_purchase_order_number_format(_invoice(None)) == []
    assert is_valid_purchase_order_number(None) is False


@pytest.mark.parametrize(
    "placeholder",
    [
        "N/A",
        "n/a",
        "NA",
        "None",
        "none",
        "NULL",
        "null",
        "nil",
        "Unknown",
        "UNKNOWN",
        "TBD",
        "tbd",
        "Pending",
        "PENDING",
        "VOID",
        "Sample",
        "test",
        "undefined",
        "Not Applicable",
        "not available",
        "unassigned",
        "No PO",
        "no p.o.",
        "None Required",
        "Verbal",
        "verbal po",
    ],
)
def test_check_purchase_order_number_triggers_on_placeholders(
    placeholder: str,
) -> None:
    findings = check_purchase_order_number_format(_invoice(placeholder))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "invalid_purchase_order_number"
    assert finding.severity == "medium"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == (
        "invoice.purchase_order_number is a valid alphanumeric identifier and not a placeholder"
    )
    assert finding.observed_value == placeholder
    assert finding.expected_value == "valid purchase order number"
    assert finding.details == {
        "field": "purchase_order_number",
        "purchase_order_number": placeholder,
        "reason": "placeholder",
    }
    assert "generic placeholder token" in finding.explanation
    assert is_valid_purchase_order_number(placeholder) is False


@pytest.mark.parametrize(
    "generic_label",
    [
        "PO",
        "po",
        "PO Number",
        "PO NO",
        "PO #",
        "PO Num",
        "Purchase Order",
        "PURCHASE ORDER",
        "Purchase Order Number",
        "Purchase Order No",
        "Purchase Order #",
        "P.O.",
        "p.o.",
        "P.O. #",
        "P.O. NO",
        "Order Number",
        "Order No",
        "ORDER #",
        "Order",
        "PO/SO",
        "SO",
    ],
)
def test_check_purchase_order_number_triggers_on_generic_labels(
    generic_label: str,
) -> None:
    findings = check_purchase_order_number_format(_invoice(generic_label))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "invalid_purchase_order_number"
    assert finding.severity == "medium"
    assert finding.details["reason"] == "generic_label"
    assert "document header label" in finding.explanation
    assert is_valid_purchase_order_number(generic_label) is False


@pytest.mark.parametrize(
    "blank_or_punct",
    [
        "",
        "   ",
        "-",
        "--",
        "---",
        ".",
        "...",
        "/",
        "//",
        "_",
        "- - -",
        "#",
    ],
)
def test_check_purchase_order_number_triggers_on_blank_or_punctuation(
    blank_or_punct: str,
) -> None:
    findings = check_purchase_order_number_format(_invoice(blank_or_punct))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "invalid_purchase_order_number"
    assert finding.severity == "medium"
    assert finding.details["reason"] == "blank_or_punctuation"
    assert "no alphanumeric characters" in finding.explanation
    assert is_valid_purchase_order_number(blank_or_punct) is False


@pytest.mark.parametrize(
    "control_str",
    [
        "PO-001\nLine2",
        "PO\r\n001",
        "PO\t001",
        "PO-001\x00",
        "PO-001\x1b",
    ],
)
def test_check_purchase_order_number_triggers_on_control_characters(
    control_str: str,
) -> None:
    findings = check_purchase_order_number_format(_invoice(control_str))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "invalid_purchase_order_number"
    assert finding.severity == "medium"
    assert finding.details["reason"] == "control_characters"
    assert "invalid control characters" in finding.explanation
    assert is_valid_purchase_order_number(control_str) is False


def test_check_purchase_order_number_triggers_on_excessive_length() -> None:
    long_number = "P" * (MAX_PURCHASE_ORDER_NUMBER_LENGTH + 1)
    findings = check_purchase_order_number_format(_invoice(long_number))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "invalid_purchase_order_number"
    assert finding.severity == "medium"
    assert finding.details["reason"] == "excessive_length"
    assert "exceeds the maximum allowed length" in finding.explanation
    assert is_valid_purchase_order_number(long_number) is False

    # Exact boundary: length == 64 is permitted
    boundary_number = "P" * MAX_PURCHASE_ORDER_NUMBER_LENGTH
    assert check_purchase_order_number_format(_invoice(boundary_number)) == []
    assert is_valid_purchase_order_number(boundary_number) is True

    # Custom max length
    assert (
        check_purchase_order_number_format(_invoice("PO-1234567"), max_length=5) != []
    )
    assert (
        check_purchase_order_number_format(_invoice("PO-1234567"), max_length=15) == []
    )


def test_check_purchase_order_number_preserves_input_immutability() -> None:
    invoice = _invoice("N/A")
    original_dict = copy.deepcopy(invoice.model_dump())
    findings = check_purchase_order_number_format(invoice)
    assert len(findings) == 1
    assert invoice.model_dump() == original_dict
    assert MAX_PURCHASE_ORDER_NUMBER_LENGTH == 64


# ---------------------------------------------------------------------------
# Service Integration & Verdict
# ---------------------------------------------------------------------------


class _FakeInvoiceRepository:
    """Minimal repository fake for service integration tests."""

    def list_vendor_invoices(self, vendor_key: str) -> list[object]:
        return []

    def get_purchase_order(self, vendor_key: str, po_number: str) -> object | None:
        return None


def test_verification_service_reports_invalid_purchase_order_number() -> None:
    from veridoc.processing.verdict import derive_verdict
    from veridoc.verification.service import VerificationService

    service = VerificationService(repository=_FakeInvoiceRepository())  # type: ignore[arg-type]

    result = service.verify(_invoice("N/A"))
    findings = [
        f for f in result.findings if f.finding_type == "invalid_purchase_order_number"
    ]

    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert findings[0].details["reason"] == "placeholder"
    verdict = derive_verdict(result)
    assert verdict.status == "review_required"


def test_verification_service_accepts_valid_purchase_order_number() -> None:
    from veridoc.verification.service import VerificationService

    service = VerificationService(repository=_FakeInvoiceRepository())  # type: ignore[arg-type]

    result = service.verify(_invoice("PO-12345"))
    findings = [
        f for f in result.findings if f.finding_type == "invalid_purchase_order_number"
    ]

    assert findings == []


def test_verification_service_accepts_absent_purchase_order_number() -> None:
    from veridoc.verification.service import VerificationService

    service = VerificationService(repository=_FakeInvoiceRepository())  # type: ignore[arg-type]

    result = service.verify(_invoice(None))
    findings = [
        f for f in result.findings if f.finding_type == "invalid_purchase_order_number"
    ]

    assert findings == []
