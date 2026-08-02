# 0005: Use review-required processing verdicts

## Status

Accepted

## Context

Phase 5 must deliver one complete invoice-processing result through a public
API and a small local review interface. Deterministic verification can identify
failed checks, but the current version has no authority, policy, or human-review
workflow for automatically accepting, rejecting, or paying an invoice. The
delivery boundary must expose evidence and explanations without treating a lack
of findings as a claim that a document is trustworthy.

## Decision

Return a strict `ProcessingResult` containing the extraction and its evidence,
canonical verification findings, explanations, and a deterministic verdict.
Use `review_required` whenever one or more verification findings exist; report
their count and highest severity. Use `clear` only when the deterministic checks
return no findings, and define it as "no findings require review," not approval
or trust.

Expose the result through `POST /process` and a no-build `GET /review` page. The
page submits the selected local document to `/process` and renders response text
with DOM text nodes. It creates no review record or approval action.

## Alternatives considered

- Automatically accept invoices with no findings.
- Automatically reject invoices with high-severity findings.
- Add a persistent review queue and approval workflow before it is required.

## Consequences

The API and page make the current deterministic evidence actionable while
preserving a human review decision. Consumers must not interpret `clear` as a
guarantee of correctness or fraud absence. A later approved workflow may add
identity, policy, assignment, state transitions, and audit retention without
changing the facts delivered by `ProcessingResult`.
