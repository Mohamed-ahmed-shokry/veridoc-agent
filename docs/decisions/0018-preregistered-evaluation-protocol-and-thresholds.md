# 0018: Use a preregistered evaluation protocol with explicit acceptance thresholds and slice governance

## Status

Accepted

## Context

Deciding whether the Veridoc document-intelligence system is ready for invoice and
purchase-order reconciliation cannot rely on informal demos, overall aggregate
accuracy figures, or the absence of observed bugs. Invoice processing operates
across heterogeneous document populations: languages (English, Arabic, bilingual),
scan quality (clean digital PDF vs noisy scanned raster images), layout densities,
and varied vendor formats. Without a preregistered protocol, acceptance thresholds
could be tuned after observing evaluation results, creating confirmation bias and
masking critical domain failures.

## Decision

Phase 11 adopts a preregistered evaluation protocol with explicit acceptance
thresholds, slice governance, and statistical uncertainty reporting:

1. Pre-registered Metric Categories:
   - OCR Baseline: Character Error Rate (CER) and Word Error Rate (WER) across
     Arabic, Latin, and mixed-language slices;
   - Extraction: Field-level exact match, precision, recall, F1, null-handling,
     line-item accuracy, normalized amount/date correctness, and evidence span
     grounding;
   - Deterministic Verification: True Positive Rate (TPR), True Negative Rate
     (TNR), False Positive Rate (FPR), and False Negative Rate (FNR) across
     each verification rule (arithmetic, duplicate, vendor history, purchase
     order), and deterministic verdict concordance;
   - Explanation Guardrails: Guardrail pass rate, provider-fallback adherence,
     and numerical context accuracy;
   - System Performance: P50/P95/P99 latency, throughput, concurrency limits,
     and failure budgets.

2. Slice Governance and Uncertainty:
   - Slices are declared ahead of time (`language`, `quality`, `layout`, `vendor`);
   - Each slice requires a declared minimum sample count (minimum 10 documents
     per slice for valid reporting);
   - Metrics report Wilson score confidence intervals (95% confidence level)
     or explicit standard deviations;
   - Slices failing to meet minimum sample size are explicitly marked as
     suppressed/unmeasured, not passing.

3. Objective Decision Rules:
   - `go`: All primary acceptance thresholds met across all mandatory slices;
   - `conditional_go`: Core verification meets thresholds, non-critical slices
     have documented exceptions with owners and expiration dates;
   - `no_go`: Any critical threshold (e.g. false negative verification rate > 0%,
     explanation numerical contradiction > 0%) fails.

## Alternatives considered

- Single aggregate accuracy metric without slice decomposition.
- Post-hoc threshold adjustment after inspecting initial evaluation runs.
- Subjective human review score for provider explanations.
- Omitting confidence intervals for small sample populations.

## Consequences

Evaluation is reproducible, auditable, and resistant to p-hacking. If a slice
has insufficient data or high uncertainty, the protocol prevents claiming
unconditional production readiness.
