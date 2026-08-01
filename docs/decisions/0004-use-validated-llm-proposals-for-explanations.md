# 0004: Use validated LLM proposals for explanations

## Status

Accepted

## Context

Phase 4 must explain deterministic verification findings without allowing a
model to invent statistics, override evidence, or make a contradictory factual
claim. Verification findings already contain the canonical rule, source,
severity, observed and expected values, and optional historical statistics. The
explanation layer must remain usable when a configured provider is unavailable
and must not create a public processing API before Phase 5 is approved.

## Decision

Keep `VerificationFinding` as the only factual source for an explanation.
`OpenAIResponsesExplainer` receives only canonical findings and uses structured
parsing to request one short, action-oriented guidance draft per finding. It
does not receive document bytes, rendered pages, or raw OCR text, and sets
`store=False` on the provider request.

The application validates that drafts cover every finding exactly once and
rejects narratives with numeric, comparative, or negated factual claims. The
application supplies the canonical finding and deterministically rendered
numerical context in every `FindingExplanation`. A missing, invalid, unsafe, or
unavailable provider response falls back to a deterministic explanation.

## Alternatives considered

- Return an unvalidated model-written explanation as the authoritative result.
- Avoid an LLM entirely and always use deterministic wording.
- Send OCR text or page images to the explanation provider for richer prose.

## Consequences

Phase 4 can offer optional provider-written guidance while retaining
deterministic facts and availability behavior. The conservative validation may
reject useful-sounding prose and cause a deterministic fallback, which is
preferable to an unsupported explanation. Provider use is still subject to
account, retention, regional-processing, and contractual review. Public
explanation delivery remains a Phase 5 concern.
