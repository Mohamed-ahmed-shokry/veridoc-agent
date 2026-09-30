# 0028: Detect stale invoices by issue date

## Status

Accepted

## Context

The verification layer checks internal consistency (arithmetic, dates),
vendor-history anomalies (totals, line-item prices, duplicates, payment
terms), purchase-order authorization, and vendor-registry compliance.
One category of fraud and administrative error remains undetected: an
invoice whose issue date lies far in the past relative to the current
processing date.

Two abuse patterns produce late-dated invoices:

1. **Backdating fraud** — an attacker issues an invoice dated months ago,
   hoping the stale date passes through automated controls whose operators
   assume old invoices have already been reviewed.
2. **Resubmission without reference** — a legitimate but already-paid or
   previously rejected invoice is resubmitted under its original date,
   either by accident or to obtain duplicate payment.

The existing `duplicate_invoice_number` rule catches resubmissions whose
invoice number is preserved. But an invoice without a stored number —
because it is new to this vendor in this system, or because the number
was altered — evades that check entirely. The existing `check_purchase_order`
rule catches unauthorized amounts, but only when a PO reference is present.

A stale invoice with no PO reference and a positive total has no
deterministic comparison anchor other than its own date. Flagging it for
human review is the appropriate response.

## Decision

Phase 21 adds a `stale_invoice` finding type and a pure deterministic
`check_invoice_staleness` function in `veridoc.verification.staleness`:

- The rule fires when `invoice_date` is present, the invoice date is
  strictly more than the configured staleness threshold (default 90 days)
  before the reference date, `purchase_order_number` is absent or empty,
  and `total` is present and greater than zero.
- The reference date is injected as a parameter (default `datetime.today()`)
  so the function remains purely deterministic and testable without patching.
- Severity is `medium` — the date alone is not proof of fraud, but the
  combination of age, no PO anchor, and a positive amount warrants review.
- The threshold is a module-level constant (`STALENESS_THRESHOLD_DAYS = 90`)
  with a `comparison_source` of `"invoice_fields"` and a `deterministic_rule`
  that records the threshold for traceability.
- Invoices with a PO reference are excluded: PO-anchored invoices already
  have a ceiling check, and long-running contracts routinely produce invoices
  submitted against old PO issuance dates.
- Zero-total or missing-total invoices are excluded: a zero-amount stale
  invoice is a credit note or a data artifact, not a payment risk.

`VerificationService.verify()` calls `check_invoice_staleness` after
`check_arithmetic`, passing the current date via `datetime.today()`. No
schema migration, new repository method, or threshold-calibration change is
required.

## Alternatives considered

- Apply the staleness rule to all invoices regardless of PO reference.
  Rejected: legitimate long-running contracts frequently have multi-month
  billing cycles tied to a purchase order; false positives would train
  operators to ignore the finding.
- Make the threshold configurable via an environment variable at startup.
  Rejected: the threshold is a business policy parameter, not a runtime
  tuning knob; operator confusion from a misconfigured threshold outweighs
  the flexibility benefit. The constant is documented in the ADR and can
  be changed by code review.
- Add a new `comparison_source` value for date-based rules.
  Rejected: `"invoice_fields"` already captures self-referential checks
  that use only fields extracted from the invoice itself; staleness shares
  this property.

## Consequences

Stale invoices submitted without a PO reference and a positive total now
produce a `medium` finding that routes them to human review. Invoices with
a PO reference, a zero or absent total, or an invoice date within the
90-day window are unaffected. The `FindingType` union gains one literal;
the `VerificationResult` and `ProcessingResult` schemas are unchanged; no
migration, new route, or console change is needed. The rule is covered by
the existing deterministic test pattern used throughout the verification
module.
