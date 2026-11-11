"""Tests for deterministic invoice number syntax, length, and placeholder verification."""

from __future__ import annotations

import copy

import pytest

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.invoice_number import (
    MAX_INVOICE_NUMBER_LENGTH,
    check_invoice_number_format,
)


def _invoice(invoice_number: str | None) -> InvoiceExtraction:
    return InvoiceExtraction(
        document_type="invoice",
        invoice_number=invoice_number,
    )


@pytest.mark.parametrize(
    "valid_number",
    [
        "INV-2026-001",
        "987654",
        "A/102-B",
        "REC-009",
        "PO-99124-INV",
        "ACME-4451",
        "123",
        "INV.2026.01",
        "FA/2026/0098",
        "SI-88712-X",
    ],
)
def test_check_invoice_number_passes_on_valid_numbers(valid_number: str) -> None:
    assert check_invoice_number_format(_invoice(valid_number)) == []


def test_check_invoice_number_passes_on_absent_number() -> None:
    assert check_invoice_number_format(_invoice(None)) == []


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
    ],
)
def test_check_invoice_number_triggers_on_placeholders(placeholder: str) -> None:
    findings = check_invoice_number_format(_invoice(placeholder))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "invalid_invoice_number"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == (
        "invoice.invoice_number is a valid alphanumeric identifier and not a placeholder"
    )
    assert finding.observed_value == placeholder
    assert finding.expected_value == "valid invoice number"
    assert finding.details == {
        "field": "invoice_number",
        "invoice_number": placeholder,
        "reason": "placeholder",
    }
    assert "generic placeholder token" in finding.explanation


@pytest.mark.parametrize(
    "generic_label",
    [
        "INVOICE",
        "invoice",
        "Invoice Number",
        "INVOICE NO",
        "Invoice #",
        "INV",
        "inv no",
        "INV #",
        "Bill",
        "Bill No",
        "BILL #",
        "Number",
        "no",
    ],
)
def test_check_invoice_number_triggers_on_generic_labels(generic_label: str) -> None:
    findings = check_invoice_number_format(_invoice(generic_label))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "invalid_invoice_number"
    assert finding.severity == "high"
    assert finding.details["reason"] == "generic_label"
    assert "document header label" in finding.explanation


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
def test_check_invoice_number_triggers_on_blank_or_punctuation(
    blank_or_punct: str,
) -> None:
    findings = check_invoice_number_format(_invoice(blank_or_punct))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "invalid_invoice_number"
    assert finding.severity == "high"
    assert finding.details["reason"] == "blank_or_punctuation"
    assert "no alphanumeric characters" in finding.explanation


@pytest.mark.parametrize(
    "control_str",
    [
        "INV-001\nLine2",
        "INV\r\n001",
        "INV\t001",
        "INV-001\x00",
        "INV-001\x1b",
    ],
)
def test_check_invoice_number_triggers_on_control_characters(control_str: str) -> None:
    findings = check_invoice_number_format(_invoice(control_str))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "invalid_invoice_number"
    assert finding.severity == "high"
    assert finding.details["reason"] == "control_characters"
    assert "invalid control characters" in finding.explanation


def test_check_invoice_number_triggers_on_excessive_length() -> None:
    long_number = "A" * (MAX_INVOICE_NUMBER_LENGTH + 1)
    findings = check_invoice_number_format(_invoice(long_number))
    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "invalid_invoice_number"
    assert finding.severity == "high"
    assert finding.details["reason"] == "excessive_length"
    assert "exceeds the maximum allowed length" in finding.explanation

    # Exact boundary: length == 64 is permitted
    boundary_number = "A" * MAX_INVOICE_NUMBER_LENGTH
    assert check_invoice_number_format(_invoice(boundary_number)) == []

    # Custom max length
    assert check_invoice_number_format(_invoice("ABC1234567"), max_length=5) != []
    assert check_invoice_number_format(_invoice("ABC1234567"), max_length=15) == []


def test_check_invoice_number_preserves_input_immutability() -> None:
    invoice = _invoice("N/A")
    original_dict = copy.deepcopy(invoice.model_dump())
    findings = check_invoice_number_format(invoice)
    assert len(findings) == 1
    assert invoice.model_dump() == original_dict
    assert MAX_INVOICE_NUMBER_LENGTH == 64
