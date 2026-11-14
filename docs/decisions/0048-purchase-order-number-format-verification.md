# 0048: Purchase order number format and placeholder verification

## Status

Accepted

## Context

In accounts payable (AP) automation, enterprise resource planning (ERP) systems, and financial
reconciliation, `purchase_order_number` identifies the authorizing commercial contract or procurement
requisition against which goods or services were delivered. In two-way and three-way matching, it serves
as the foreign lookup key to verify unit pricing, line item authorization, committed spend ceilings,
and vendor agreement terms.

Furthermore, within Veridoc's verification engine, the presence of a purchase order reference provides
an anchor that exempts genuine contracts from stale-invoice flags (`check_invoice_staleness`), because
contracted, milestone-based services routinely deliver invoices well after the initial purchase order
issue date.

However, multimodal vision and OCR extraction models frequently capture non-identifying or corrupted
values into the `purchase_order_number` field:
1. **Generic Placeholders**: Models transcribe `"N/A"`, `"NA"`, `"NONE"`, `"NULL"`, `"NIL"`,
   `"UNKNOWN"`, `"TBD"`, `"PENDING"`, `"VOID"`, `"SAMPLE"`, `"TEST"`, `"UNDEFINED"`, `"NOT APPLICABLE"`,
   `"NOT AVAILABLE"`, `"UNASSIGNED"`, `"NO PO"`, `"NO P.O."`, or `"NONE REQUIRED"` when no purchase
   order reference exists on the physical or visual document.
2. **Field Labels Extracted as Values**: Models transcribe the printed table header or box label
   itself—such as `"PO"`, `"PO NUMBER"`, `"PO NO"`, `"PO #"`, `"PO NUM"`, `"PURCHASE ORDER"`,
   `"PURCHASE ORDER NUMBER"`, `"PURCHASE ORDER NO"`, `"PURCHASE ORDER #"`, `"P.O."`, `"P.O. #"`,
   `"P.O. NO"`, `"ORDER NUMBER"`, `"ORDER NO"`, `"ORDER #"`, `"ORDER"`, or `"PO/SO"`—when visual
   alignment is imperfect.
3. **Blank or Punctuation-Only Strings**: Vision extractors capture raw dashes, hyphens, slashes, or
   periods (`"-"`, `"---"`, `"/"`, `"."`, `"..."`) or whitespace-only strings (`"   "`).
4. **Control Characters & Line Breaks**: Text spans captured across table cells containing embedded
   newlines (`\n`, `\r`) or unprintable control characters.
5. **Runaway OCR Paragraphs**: Text captures where OCR captures terms paragraphs, shipment addresses,
   or notes into the purchase order field (exceeding standard length bounds).

Allowing these corrupted values into the verification pipeline creates several hazards:
- **Misleading Mismatch Findings**: When an invoice carries `purchase_order_number: "N/A"`, downstream
  PO matching queries the repository for a purchase order named `"N/A"`. It fails to find it and reports
  `purchase_order_mismatch` ("No matching purchase order was found for the extracted PO number").
  This is misleading: the document did not cite an unregistered purchase order; the extracted string was
  simply a placeholder.
- **Evaded Staleness Detection**: In `check_invoice_staleness`, any non-empty string in
  `invoice.purchase_order_number` is currently treated as an anchor, allowing backdated invoices with
  placeholders like `"N/A"` to bypass staleness checks completely.
- **Unchecked Unresolved Invoices**: When vendor entity resolution cannot identify a vendor,
  `check_purchase_order` returns early, allowing corrupted and runaway PO numbers to clear without review.

Establishing a deterministic verification rule for purchase order number syntax, length, and placeholder
detection ensures that any invoice with an invalid PO reference is flagged with `medium` severity, routing
it to human review (`review_required`).

## Decision

Phase 42 introduces:

1. **`invalid_purchase_order_number` finding type**:
   - Added to `FindingType` in `veridoc.verification.models`.
   - Comparison source: `"invoice_fields"`.
   - Severity: `"medium"`.
   - Deterministic rule: `"invoice.purchase_order_number is a valid alphanumeric identifier and not a placeholder"`.
   - Structured details include:
     `"field": "purchase_order_number"`, `"purchase_order_number"`, and `"reason"`.

2. **Categorized invalidity reasons**:
   - `"control_characters"`: String contains embedded newlines (`\n`, `\r`), tabs (`\t`), or Unicode control characters.
   - `"blank_or_punctuation"`: String is empty, whitespace-only, or contains zero alphanumeric characters.
   - `"excessive_length"`: Cleaned string length exceeds `max_length` (default 64 characters).
   - `"placeholder"`: Exact case-insensitive match against canonical placeholder tokens (`n/a`, `na`, `none`, `null`, `nil`, `unknown`, `tbd`, `pending`, `void`, `sample`, `test`, `undefined`, `not applicable`, `not available`, `unassigned`, `no po`, `no p.o.`, `none required`).
   - `"generic_label"`: Exact case-insensitive match against generic header tokens (`po`, `po number`, `po no`, `po #`, `po num`, `purchase order`, `purchase order number`, `purchase order no`, `purchase order #`, `p.o.`, `p.o. #`, `p.o. no`, `order number`, `order no`, `order #`, `order`, `po/so`, `so`).

3. **Absent field handling**:
   - When `invoice.purchase_order_number is None`, zero findings are emitted. Non-PO invoices are valid in commercial practice; mandatory PO enforcement belongs to procurement policy rather than document syntax validation.

4. **Pure validation helper**:
   - `is_valid_purchase_order_number(raw_value: str | None, max_length: int = 64) -> bool` returns `True` only when `raw_value` is non-empty, contains alphanumeric characters, has no control characters, does not exceed `max_length`, and does not match placeholder or generic label tokens.

5. **Integration**:
   - `check_purchase_order_number_format(invoice)` runs in `VerificationService.verify()`.
   - When `check_purchase_order_number_format` detects an invalid PO number, `check_purchase_order` skips repository lookup to prevent redundant and misleading `purchase_order_mismatch` findings.

## Consequences

- Prevents generic placeholder tokens from masquerading as authentic purchase order references.
- Flags corrupted and runaway OCR captures in `purchase_order_number`.
- Preserves full backward compatibility: genuine alphanumeric purchase orders (e.g. `PO-12345`, `PO/2026/099`, `4500012345`) continue to clear without findings.
- Input invoice models remain strictly immutable.
