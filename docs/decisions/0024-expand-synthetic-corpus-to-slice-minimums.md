# 0024: Expand the synthetic corpus to slice minimums with committed construction

## Status

Accepted

## Context

The Phase 11 readiness decision (`docs/evaluation-report.md`) is
`conditional_go` with a single blocking condition: every slice holds fewer
samples than the preregistered minimum of 10 (`eng` 2, `ara` 1, `clean` 2,
`noisy` 1, `standard` 2, `dense` 1 across 3 documents). Remediation must add
17 documents without weakening corpus governance (ADR 0020): 100% synthetic
data, SHA-256-bound manifests, deterministic construction, and no new
licenses or dependencies.

Two construction constraints shape the method. First, Arabic documents must
carry genuinely shaped Arabic script: Pillow's default bitmap font and
unshaped code-point rendering would commit tofu boxes or misordered glyphs,
poisoning future OCR measurement. No Arabic-capable font is guaranteed on
every developer machine or CI runner, and adding font or reshaping
dependencies for fixtures alone is unjustified. Second, the committed bytes
must be reproducible from reviewed construction code, not opaque hand-made
binaries that no one can regenerate or audit.

## Decision

Phase 13 expands the corpus to 20 documents (`veridoc-synthetic-benchmark-v2`)
using committed deterministic construction only:

- Latin invoice lines render with the Pillow default bitmap font, matching the
  existing `doc_001` style byte-for-byte in method;
- Arabic content is composed by pixel-splicing the verified `doc_003`
  rendering (genuinely shaped script produced once on an Arabic-capable host)
  with newly rendered Latin invoice lines, so every committed Arabic pixel is
  real shaped script and every varying field stays deterministic;
- `noisy` variants apply deterministic Pillow transforms (small rotation,
  contrast reduction, mild blur) to clean compositions;
- `dense` variants use compact multi-column Latin layouts at tighter spacing;
- multi-page PDFs embed composed page images or deterministic
  PyMuPDF text pages, keeping Arabic pages as embedded images;
- each document ships complete ground truth (fields, line items, expected
  findings, expected verdict, OCR transcript) with self-consistent arithmetic;
- the construction script lives with the corpus (`tests/fixtures/corpus/`)
  and is documented in the fixture guide; tests and the benchmark consume
  only the committed bytes and never require fonts; and
- the runner buckets the protocol's fourth dimension, page count
  (`single` for one page, `multi` otherwise), alongside language, quality,
  and layout.

Slice balance is exact: 10 `eng` / 10 `ara`, 10 `clean` / 10 `noisy`,
10 `standard` / 10 `dense`, and 10 `single` / 10 `multi` (counting the three
Phase 11 documents).

## Alternatives considered

- Render new Arabic text with Pillow's default font, accepting tofu boxes.
- Add an Arabic TTF plus reshaping libraries as fixture dependencies.
- Commit opaque hand-made binaries with no construction script.
- Expand only `eng` slices and leave `ara` under-sampled.

## Consequences

The remediation corpus meets every preregistered minimum while keeping
governance, determinism, and dependency discipline intact. Pixel-splicing
bounds Arabic diversity to compositions of one verified rendering, which the
corpus documentation states openly; broader Arabic generation awaits a
properly licensed font and shaping stack in a later phase. The fake-harness
benchmark validates plumbing only — the Tesseract-measured re-run and the
resulting decision update remain an operator step in the equipped
environment, recorded as the recommended Phase 14.
