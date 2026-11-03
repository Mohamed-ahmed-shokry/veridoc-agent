# Phase 36 Progress Record: Vendor VAT Identifier Format Verification

## Phase Overview

- **Phase:** Phase 36
- **Goal:** Introduce deterministic national VAT number structure verification (ADR 0042) for extracted vendor tax IDs, routing corrupted OCR reads and fabricated tax identifiers to review independently of vendor registry availability.
- **Status:** Complete
- **Branch:** `phase/vat-format-verification`
- **Draft PR:** [#13](https://github.com/Mohamed-ahmed-shokry/veridoc-agent/pull/13)
- **Base:** `phase/iban-checksum-verification` (stacked on Phase 35, PR #12)

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Define Phase 36 specification in `docs/roadmap.md` and record ADR 0042 | Completed | `bca7138`, `0aa8774` |
| 2 | Register ADR 0042 in the decisions index | Completed | `0942efe` |
| 3 | Add `invalid_tax_id` to `FindingType` with a model test | Completed | `fb805bf`, `9fd8423`, `4a9049b` |
| 4 | Add per-country VAT structure table | Completed | `b6a0f9b` |
| 5 | Implement `check_tax_id_format` rule | Completed | `9eb4952` |
| 6 | Add unit tests covering all paths and input immutability | Completed | `2ac2ab2` |
| 7 | Register test module in documentation | Completed | `0b5f3d4` |
| 8 | Integrate rule into `VerificationService.verify()` | Completed | `3b648b2` |
| 9 | Add `VerificationService` integration and verdict tests | Completed | `3fb8a60` |
| 10 | Update README, CHANGELOG, architecture, AGENTS, and roadmap | Completed | `36ef13f`..`0b24d5b`, `63bb6d0` |
| 11 | Upgrade `langgraph-sdk` and `msgpack` to resolve security advisories | Completed | `0a870b6` |
| 12 | Verify local CI parity and record release evidence | Completed | `4fd79bd` |
| 13 | Finalize progress record with validation evidence | Completed | this commit |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `invalid_tax_id` appears in `FindingType` and is accepted by `VerificationFinding` | Verified | `tests/test_verification_models.py` passed |
| 2 | Structurally valid VAT numbers (spaced, punctuated, lowercase) produce no finding for every table country | Verified | `tests/test_verification_tax_id.py` passed |
| 3 | A recognized-prefix identifier with the wrong structure produces one `medium` finding with `field`, normalized `tax_id`, and `country` | Verified | `tests/test_verification_tax_id.py` passed |
| 4 | Absent, blank, and unrecognized-prefix (domestic) identifiers produce no finding | Verified | `tests/test_verification_tax_id.py` passed |
| 5 | The check does not mutate the input extraction | Verified | `tests/test_verification_tax_id.py` passed |
| 6 | `VerificationService.verify()` reports the finding and routes to `review_required` | Verified | `tests/test_verification_tax_id.py` passed |
| 7 | All local CI-parity checks and remote CI workflow runs pass 100% | Verified | 1490 tests passed locally; quality gate green |

## Decision Log

### Decision 1: Validate VAT structure via compiled per-country regex patterns
- **Context:** OCR misreads often scramble letters/digits or alter string lengths in European VAT identifiers. Invoices without reference-data vendor records bypass vendor master reconciliation.
- **Decision:** Implement `check_tax_id_format` in `veridoc.verification.tax_id` with regex patterns covering EU member states, the UK (`GB`), and Northern Ireland (`XI`), mapping Greece to the `EL` prefix.
- **Alternatives Considered:** Complete per-country checksum verification. Rejected: per-country algorithms are varied, complex, frequently revised, and brittle.
- **Blast Radius & Reversibility:** Pure function, additive finding type, no schema or API changes.

### Decision 2: Ignore absent, blank, and unrecognized-prefix tax identifiers
- **Context:** Non-European jurisdictions use formats (like US EIN `XX-XXXXXXX`) that do not start with a 2-letter country prefix.
- **Decision:** Strip whitespace and punctuation. If the prefix is not in `VAT_STRUCTURES`, return `[]` without error or finding.
- **Alternatives Considered:** Flagging any non-matching tax ID. Rejected: false positives on valid domestic non-EU tax IDs.
- **Blast Radius & Reversibility:** Scoped strictly to recognizable European VAT prefixes.

### Decision 3: Assign `medium` severity to `invalid_tax_id` findings
- **Context:** A malformed VAT identifier indicates either an OCR read error or a malformed document. Unlike an impossible IBAN which prevents payment execution, an invalid VAT ID requires review and tax correction.
- **Decision:** Assign `medium` severity to `invalid_tax_id`, ensuring routing to `review_required` in `derive_verdict`.
- **Alternatives Considered:** `high` severity. Rejected: reserving `high` for critical payment redirection or missing core identifiers.
- **Blast Radius & Reversibility:** Consistent with verification severity design.

### Decision 4: Upgrade `langgraph-sdk` and `msgpack` dependencies
- **Context:** CI security audit failed due to CVE-2026-118667 in `langgraph-sdk` and CVE-2026-114613 in `msgpack`.
- **Decision:** Run `uv lock --upgrade-package langgraph-sdk --upgrade-package msgpack` upgrading to safe versions (0.4.10 and 1.2.4).
- **Alternatives Considered:** Suppressing audit or waiting. Rejected: violates Rule #2 and honesty contracts.
- **Blast Radius & Reversibility:** Lockfile-only change, verified with full test suite.

### Decision 5: Stack Phase 36 on Phase 35 branch
- **Context:** Phase 36 is the counterpart of Phase 35, following the roadmap order.
- **Decision:** Branch `phase/vat-format-verification` from `phase/iban-checksum-verification` and open PR #13 with base `phase/iban-checksum-verification`.
- **Alternatives Considered:** Branching from `main`. Rejected: would introduce conflicts in shared documentation and roadmap files.
- **Blast Radius & Reversibility:** Clean branch hierarchy.

## CI & Validation Log

Local commands run from the repository root on Windows with Python 3.12.12 and uv 0.9.13:

| Command | Result |
|---|---|
| `git diff --check "$(git hash-object -t tree /dev/null)" HEAD` | Passed (zero whitespace issues) |
| `uv lock --check` | Passed |
| `uv run pip-audit` | Passed (0 known vulnerabilities; `veridoc` skipped as not on PyPI) |
| `uv run ruff check .` | Passed (All checks passed!) |
| `uv run ruff format --check .` | Passed (314 files formatted) |
| `uv run mypy` | Passed (121 source files) |
| `uv run pytest -q` | 1490 passed |
| `uv run pytest --cov=veridoc` | 1490 passed; 94.08% total branch coverage (90% floor) |
| `uv run pytest tests/test_documentation.py` | 3 passed |
| `uv build --clear` | Wheel and source distribution built |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content and safety checks |
| Isolated wheel smoke test | Passed |
| Isolated source distribution smoke test | Passed |
