# Phase 34 Progress Record: Line Item Completeness and Derived Subtotals

## Phase Overview

- **Phase:** Phase 34
- **Goal:** Introduce deterministic line item completeness verification (ADR 0040) requiring a non-blank identity and either a total price or both quantity and unit price, and derive omitted line totals during subtotal verification so unidentifiable or unpriceable lines cannot clear vacuously.
- **Status:** Complete
- **Branch:** `phase/line-item-completeness`
- **Draft PR:** [#10](https://github.com/Mohamed-ahmed-shokry/veridoc-agent/pull/10)
- **Base:** `phase/required-field-completeness` (stacked on Phase 33, PR #9); retarget to `main` after Phase 33 merges.

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Define Phase 34 specification in `docs/roadmap.md` and record ADR 0040 | Completed | `8a87cf0` |
| 2 | Register ADR 0040 in the decisions index | Completed | `280503a` |
| 3 | Add `incomplete_line_item` to `FindingType` with a model test | Completed | `280503a` |
| 4 | Implement `check_line_item_completeness` | Completed | `f6f904a` |
| 5 | Add focused line item completeness tests | Completed | `f6f904a` |
| 6 | Integrate completeness into `VerificationService.verify()` | Completed | `d4816fe` |
| 7 | Add service integration and verdict tests | Completed | `d4816fe` |
| 8 | Derive omitted line totals in `check_line_items_subtotal` | Completed | `3421441` |
| 9 | Add derived subtotal and rounding tests | Completed | `3421441` |
| 10 | Update the documented test inventory | Completed | `ffb42d7` |
| 11 | Update README, CHANGELOG, architecture, AGENTS, and roadmap | Completed | `e648631`..`969f2d6` |
| 12 | Verify local CI parity and record release evidence | Completed | `4519ee0` |
| 13 | Push branch, open draft PR, and verify remote CI | Completed | CI run `39847055568` |
| 14 | Finalize this progress record | Completed | this commit |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `incomplete_line_item` appears in `FindingType` and is accepted by `VerificationFinding` | Verified | `tests/test_verification_models.py` passed |
| 2 | `check_line_item_completeness` returns `[]` for no line items and for lines with an identity and a total or quantity-plus-unit-price | Verified | `tests/test_verification_line_item_completeness.py` passed |
| 3 | Missing identity and underivable amount each yield one `medium` finding with the documented `field` | Verified | `tests/test_verification_line_item_completeness.py` passed |
| 4 | Findings follow line-item order with identity before amount; `total_price=0` counts as present | Verified | `tests/test_verification_line_item_completeness.py` passed |
| 5 | The check does not mutate the input extraction | Verified | `tests/test_verification_line_item_completeness.py` passed |
| 6 | `VerificationService.verify()` reports line item gaps and routes to `review_required` | Verified | `tests/test_verification_line_item_completeness.py` passed |
| 7 | `check_line_items_subtotal` derives `quantity * unit_price`, preserves tolerance, and flags material mismatches | Verified | `tests/test_verification_arithmetic.py` passed |
| 8 | All local CI-parity checks and remote CI workflow runs pass 100% | Verified | Local gates below; CI run [39847896182](https://github.com/Mohamed-ahmed-shokry/veridoc-agent/actions/runs/39847896182) success |

## Decision Log

### Decision 1: Require an identity for every line item
- **Context:** `line_item_key` returns `None` when both `product_identifier` and `description` are absent or blank. Duplicate detection, vendor-history occurrence, price/quantity statistics, and purchase-order line matching all skip such a line, so it can never be reconciled.
- **Decision:** Emit `incomplete_line_item` with `field="identity"` when a line has no non-blank identifier or description. Reuse `line_item_key` so blank strings count as absent exactly as in existing rules.
- **Alternatives Considered:** Requiring both identifier and description. Rejected: many legitimate invoices carry only one. Leaving unidentifiable lines to be skipped. Rejected: it is the vacuous-clear path this phase closes.
- **Blast Radius & Reversibility:** Additive finding type and pure rule; no schema or persistence change.

### Decision 2: Accept a total price or a derivable quantity-times-price amount
- **Context:** A line with only `total_price` is directly summable; a line with `quantity` and `unit_price` is deterministically derivable. A line with neither, or with only one of the two, cannot be priced.
- **Decision:** Emit `field="amount"` only when `total_price` is absent and either `quantity` or `unit_price` is also absent. Do not judge sign or value.
- **Alternatives Considered:** Requiring `total_price` unconditionally. Rejected: it would flag legitimate invoices that print quantity and unit price without a line total. Judging value here. Rejected: Phases 25 and 27 own sign and rounding.
- **Blast Radius & Reversibility:** Completeness only; existing non-positive and arithmetic rules are unchanged.

### Decision 3: Derive omitted line totals during subtotal verification
- **Context:** `check_line_items_subtotal` returned early when any `total_price` was absent, even when `quantity * unit_price` was available. One omitted line total disabled subtotal verification for the whole invoice.
- **Decision:** Add `total_price` when present and otherwise derive `quantity * unit_price`; return `[]` only when an amount remains underivable. Preserve rounding tolerance and existing finding types/severities. Update the deterministic-rule strings to state the derivation.
- **Alternatives Considered:** Keeping the early return and relying only on the new completeness rule. Rejected: a derivable line would pass completeness yet still disable the subtotal check. Flagging a missing line total as an error even when derivable. Rejected: unnecessary review noise.
- **Blast Radius & Reversibility:** One pure arithmetic function and its rule strings; covered by existing and new tests.

### Decision 4: Use medium severity and stable structured details
- **Context:** These are completeness gaps requiring human review, not confirmed fraud. The review console and evidence bundle consume `details` for filtering.
- **Decision:** Use `medium` for both requirements; details are `{"line_item_index": index, "field": "identity" | "amount"}`. Emit in line-item order with identity before amount.
- **Alternatives Considered:** `high` severity. Rejected: overstates confirmed risk and diverges from other completeness/uncertainty rules. A single aggregate finding. Rejected: loses line-level addressability.
- **Blast Radius & Reversibility:** Deterministic order and details are covered by tests.

### Decision 5: Stack Phase 34 on the unmerged Phase 33 branch
- **Context:** Phase 33 is complete and pushed on `phase/required-field-completeness` but not merged. Phase 34 follows it sequentially in the roadmap and shares documentation regions.
- **Decision:** Branch from Phase 33, open a draft PR against `phase/required-field-completeness`, and document the retarget to `main` after Phase 33 merges.
- **Alternatives Considered:** Branching from `main`. Rejected: docs would claim Phase 33 complete while the base lacks it and later doc conflicts would be likely. Including both phases in one PR against `main`. Rejected: obscures review of Phase 34.
- **Blast Radius & Reversibility:** Branch/PR base only; no code or history rewrite.

## CI & Validation Log

Local commands run from the repository root on Windows with Python 3.12.12 and uv 0.9.13:

| Command | Result |
|---|---|
| `git diff --check "$(git hash-object -t tree /dev/null)" HEAD` | Passed (no output) |
| `uv lock --check` | Passed |
| `uv run pip-audit` | Passed (0 known vulnerabilities; `veridoc` skipped as not on PyPI) |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed (310 files) |
| `uv run mypy` | Passed (119 source files) |
| `uv run pytest -q` | 1396 passed |
| `uv run pytest --cov=veridoc` | 1396 passed; 94.02% total branch coverage |
| `uv run pytest tests/test_documentation.py` | 3 passed |
| `uv build --clear` | Wheel and source distribution built |
| `uv run twine check dist/*` | Both distributions passed |
| `uv run python scripts/check_distribution.py` | Both archives passed |
| Isolated wheel smoke test | Passed |
| Isolated source-distribution smoke test | Passed |

Remote CI:

- Workflow: `CI`
- Run: [39847896182](https://github.com/Mohamed-ahmed-shokry/veridoc-agent/actions/runs/39847896182)
- Head commit: `a863194`
- Result: `success`

The container-build step runs only in GitHub Actions; local Docker is not
installed. The remote run completed that step successfully.

## Blockers

None. Phase 14 remains planned but blocked on a Tesseract-equipped operator
environment and is out of scope for this phase.
