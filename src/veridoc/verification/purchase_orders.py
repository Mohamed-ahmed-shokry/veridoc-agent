"""Deterministic invoice and purchase-order reconciliation checks."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from veridoc.extraction.models import InvoiceExtraction
from veridoc.persistence.protocol import InvoiceRepository
from veridoc.verification.line_items import line_item_key
from veridoc.verification.models import VerificationFinding
from veridoc.verification.purchase_order_number import (
    is_valid_purchase_order_number,
)
from veridoc.verification.references import (
    HistoricalInvoice,
    PurchaseOrder,
    ReferenceLineItem,
)
from veridoc.verification.vendors import vendor_key_for


def check_purchase_order(
    invoice: InvoiceExtraction, repository: InvoiceRepository
) -> list[VerificationFinding]:
    """Compare extracted invoice facts with their referenced purchase order."""
    vendor_key = vendor_key_for(invoice)
    if (
        vendor_key is None
        or invoice.purchase_order_number is None
        or not is_valid_purchase_order_number(invoice.purchase_order_number)
    ):
        return []
    purchase_order = repository.get_purchase_order(
        vendor_key, invoice.purchase_order_number
    )
    if purchase_order is None:
        return [
            VerificationFinding(
                finding_type="purchase_order_mismatch",
                severity="high",
                explanation="No matching purchase order was found for the extracted PO number.",
                comparison_source="purchase_order",
                deterministic_rule="referenced purchase order must exist for the vendor",
                observed_value=invoice.purchase_order_number,
                expected_value="matching purchase order",
                details={"vendor_key": vendor_key},
            )
        ]

    findings: list[VerificationFinding] = []
    if invoice.currency is not None and purchase_order.currency is not None:
        findings.extend(
            _mismatch_finding(
                field="currency",
                observed_value=invoice.currency,
                expected_value=purchase_order.currency,
            )
        )
    if (
        invoice.total is not None
        and purchase_order.total is not None
        and _comparable_amounts(invoice, purchase_order)
        and invoice.total > purchase_order.total
    ):
        findings.append(
            VerificationFinding(
                finding_type="purchase_order_mismatch",
                severity="high",
                explanation="The invoice total exceeds the referenced purchase order total.",
                comparison_source="purchase_order",
                deterministic_rule="invoice.total must not exceed purchase_order.total",
                observed_value=str(invoice.total),
                expected_value=str(purchase_order.total),
                details={"field": "total"},
            )
        )
    findings.extend(_check_line_items(invoice, purchase_order.line_items))
    return findings


def check_purchase_order_ceiling(
    invoice: InvoiceExtraction,
    repository: InvoiceRepository,
    history: Sequence[HistoricalInvoice],
) -> list[VerificationFinding]:
    """Flag split over-billing when prior invoices plus this one exceed the PO."""
    vendor_key = vendor_key_for(invoice)
    if (
        vendor_key is None
        or invoice.purchase_order_number is None
        or not is_valid_purchase_order_number(invoice.purchase_order_number)
    ):
        return []
    purchase_order = repository.get_purchase_order(
        vendor_key, invoice.purchase_order_number
    )
    if (
        purchase_order is None
        or purchase_order.total is None
        or invoice.total is None
        or not _comparable_amounts(invoice, purchase_order)
    ):
        return []
    billed_to_date = invoice.total
    prior_count = 0
    for prior in history:
        if prior.purchase_order_number != invoice.purchase_order_number:
            continue
        if prior.currency != invoice.currency or prior.total is None:
            continue
        billed_to_date += prior.total
        prior_count += 1
    if prior_count == 0 or billed_to_date <= purchase_order.total:
        return []
    return [
        VerificationFinding(
            finding_type="purchase_order_mismatch",
            severity="high",
            explanation="Prior invoices against this purchase order plus this invoice exceed its total.",
            comparison_source="purchase_order",
            deterministic_rule="invoiced amounts against a purchase order must not exceed the authorized total",
            observed_value=str(billed_to_date),
            expected_value=str(purchase_order.total),
            details={
                "field": "purchase_order_billed_total",
                "prior_invoice_count": prior_count,
            },
        )
    ]


def _comparable_amounts(
    invoice: InvoiceExtraction, purchase_order: PurchaseOrder
) -> bool:
    """Return whether two amounts share a known equal currency."""
    if invoice.currency is None or purchase_order.currency is None:
        return True
    return invoice.currency == purchase_order.currency


def _authorized_po_line_quantities(
    purchase_order_line_items: Sequence[ReferenceLineItem],
) -> dict[str, Decimal]:
    """Sum authorized PO quantities per line-item key, skipping keys with None."""
    totals: dict[str, Decimal] = {}
    unknown_keys: set[str] = set()
    for item in purchase_order_line_items:
        key = line_item_key(item.product_identifier, item.description)
        if key is None:
            continue
        if item.quantity is None:
            unknown_keys.add(key)
            totals.pop(key, None)
            continue
        if key not in unknown_keys:
            totals[key] = totals.get(key, Decimal(0)) + item.quantity
    return totals


def _prior_po_line_quantities(
    invoice: InvoiceExtraction,
    history: Sequence[HistoricalInvoice],
    tracked_keys: set[str],
) -> tuple[dict[str, Decimal], dict[str, int]]:
    """Aggregate prior billed quantities and invoice counts per tracked line-item key."""
    prior_quantities: dict[str, Decimal] = {}
    prior_invoice_counts: dict[str, int] = {}
    for prior in history:
        if prior.purchase_order_number != invoice.purchase_order_number:
            continue
        if (
            invoice.currency is not None
            and prior.currency is not None
            and prior.currency != invoice.currency
        ):
            continue
        seen_in_prior: set[str] = set()
        for item in prior.line_items:
            key = line_item_key(item.product_identifier, item.description)
            if key is None or item.quantity is None or key not in tracked_keys:
                continue
            prior_quantities[key] = (
                prior_quantities.get(key, Decimal(0)) + item.quantity
            )
            seen_in_prior.add(key)
        for key in seen_in_prior:
            prior_invoice_counts[key] = prior_invoice_counts.get(key, 0) + 1
    return prior_quantities, prior_invoice_counts


def _check_line_item_quantity_ceilings(
    invoice: InvoiceExtraction,
    purchase_order: PurchaseOrder,
    history: Sequence[HistoricalInvoice],
) -> list[VerificationFinding]:
    """Flag split over-billing when cumulative line-item quantity exceeds the PO."""
    authorized_quantities = _authorized_po_line_quantities(purchase_order.line_items)
    if not authorized_quantities:
        return []

    current_quantities: dict[str, Decimal] = {}
    for item in invoice.line_items:
        key = line_item_key(item.product_identifier, item.description)
        if key is None or item.quantity is None or key not in authorized_quantities:
            continue
        current_quantities[key] = (
            current_quantities.get(key, Decimal(0)) + item.quantity
        )
    if not current_quantities:
        return []

    prior_quantities, prior_invoice_counts = _prior_po_line_quantities(
        invoice, history, set(current_quantities)
    )
    findings: list[VerificationFinding] = []
    for key, current_quantity in current_quantities.items():
        prior_count = prior_invoice_counts.get(key, 0)
        if prior_count == 0:
            continue
        billed_quantity = prior_quantities[key] + current_quantity
        authorized_quantity = authorized_quantities[key]
        if billed_quantity <= authorized_quantity:
            continue
        findings.append(
            VerificationFinding(
                finding_type="purchase_order_mismatch",
                severity="high",
                explanation=(
                    "Prior invoices against this purchase order plus this invoice "
                    f"exceed the authorized quantity for '{key}'."
                ),
                comparison_source="purchase_order",
                deterministic_rule=(
                    "invoiced line-item quantities against a purchase order "
                    "must not exceed the authorized quantity"
                ),
                observed_value=str(billed_quantity),
                expected_value=str(authorized_quantity),
                details={
                    "field": "purchase_order_billed_line_item_quantity",
                    "line_item_key": key,
                    "prior_invoice_count": prior_count,
                },
            )
        )
    return findings


def _mismatch_finding(
    *, field: str, observed_value: str, expected_value: str
) -> list[VerificationFinding]:
    if observed_value == expected_value:
        return []
    return [
        VerificationFinding(
            finding_type="purchase_order_mismatch",
            severity="high",
            explanation=f"The invoice {field} does not match the referenced purchase order.",
            comparison_source="purchase_order",
            deterministic_rule=f"invoice.{field} == purchase_order.{field}",
            observed_value=observed_value,
            expected_value=expected_value,
            details={"field": field},
        )
    ]


def _check_line_items(
    invoice: InvoiceExtraction, purchase_order_line_items: list[ReferenceLineItem]
) -> list[VerificationFinding]:
    findings: list[VerificationFinding] = []
    remaining_purchase_order_line_items = list(purchase_order_line_items)
    for index, invoice_line_item in enumerate(invoice.line_items):
        key = line_item_key(
            invoice_line_item.product_identifier, invoice_line_item.description
        )
        if key is None:
            continue
        matching_index = next(
            (
                candidate_index
                for candidate_index, purchase_order_line_item in enumerate(
                    remaining_purchase_order_line_items
                )
                if line_item_key(
                    purchase_order_line_item.product_identifier,
                    purchase_order_line_item.description,
                )
                == key
            ),
            None,
        )
        if matching_index is None:
            findings.append(
                VerificationFinding(
                    finding_type="purchase_order_mismatch",
                    severity="high",
                    explanation="The invoice line item does not appear on the referenced purchase order.",
                    comparison_source="purchase_order",
                    deterministic_rule="invoice line item must exist on purchase order",
                    observed_value=key,
                    expected_value="matching purchase-order line item",
                    details={"field": "line_item", "line_item_index": index},
                )
            )
            continue
        matching_purchase_order_line_item = remaining_purchase_order_line_items.pop(
            matching_index
        )
        observed_quantity = invoice_line_item.quantity
        expected_quantity = matching_purchase_order_line_item.quantity
        if (
            observed_quantity is not None
            and expected_quantity is not None
            and observed_quantity > expected_quantity
        ):
            findings.append(
                VerificationFinding(
                    finding_type="purchase_order_mismatch",
                    severity="high",
                    explanation="The invoice line-item quantity exceeds the purchase order.",
                    comparison_source="purchase_order",
                    deterministic_rule="invoice.line_item.quantity must not exceed purchase_order.line_item.quantity",
                    observed_value=str(observed_quantity),
                    expected_value=str(expected_quantity),
                    details={"field": "line_item_quantity", "line_item_index": index},
                )
            )
        observed_price = invoice_line_item.unit_price
        expected_price = matching_purchase_order_line_item.unit_price
        if (
            observed_price is not None
            and expected_price is not None
            and observed_price != expected_price
        ):
            findings.append(
                VerificationFinding(
                    finding_type="purchase_order_mismatch",
                    severity="high",
                    explanation="The invoice line-item unit price does not match the purchase order.",
                    comparison_source="purchase_order",
                    deterministic_rule="invoice.line_item.unit_price == purchase_order.line_item.unit_price",
                    observed_value=str(observed_price),
                    expected_value=str(expected_price),
                    details={
                        "field": "line_item_unit_price",
                        "line_item_index": index,
                    },
                )
            )
    return findings
