# Veridoc Evaluation Protocol & Thresholds

## Overview & Scope

Per ADR 0018, this document preregisters the comprehensive evaluation protocol,
metrics definitions, acceptance thresholds, uncertainty quantification methods,
and decision rules for the Veridoc document intelligence system.

Veridoc is an agentic document-intelligence system designed to determine whether
data extracted from invoices and purchase orders can be trusted. It is not a
generic extraction platform; its version 1 scope is strictly accounts-payable
reconciliation, deterministic factual verification, and evidence-grounded
findings.

---

## Evaluation Corpus Governance

Per ADR 0020, evaluation uses a versioned manifest with cryptographic integrity
guarantees:

1. **Synthetic & Permissive Data Only**: The evaluation corpus consists
   exclusively of synthetic fixtures and verified open-access documents. No real
   customer invoices, PII, financial secrets, or proprietary data are included.
2. **Cryptographic Verification**: Every document and ground-truth file is
   hashed with SHA-256 upon ingestion. Manifests (`manifest.json`) record
   document IDs, MIME types, relative paths, and SHA-256 digests. Any file
   modification or missing asset causes `CorpusIntegrityError`.
3. **Data Slices**: The corpus covers four orthogonal operational dimensions:
   - **Language**: English (`eng`) and Arabic (`ara`).
   - **Image Quality**: `clean` (high-DPI, clear contrast) and `noisy` (skew,
     contrast degradation, compression artifacts).
   - **Layout Complexity**: `standard` (linear, predictable tabular layouts) and
     `dense` (compact multi-column or clustered layouts).
   - **Document Length**: Single-page and multi-page (`page_count >= 2`).

---

## Preregistered Metrics & Mathematical Definitions

### 1. OCR Error Rates
- **Character Error Rate (CER)**:
  $$\text{CER} = \frac{\text{LevenshteinDistance}(\text{ref\_chars}, \text{hyp\_chars})}{\max(1, \text{len}(\text{ref\_chars}))}$$
- **Word Error Rate (WER)**:
  $$\text{WER} = \frac{\text{LevenshteinDistance}(\text{ref\_words}, \text{hyp\_words})}{\max(1, \text{len}(\text{ref\_words}))}$$

### 2. Structured Extraction Metrics
- **Field Precision ($P$)**: True Positives / (True Positives + False Positives).
- **Field Recall ($R$)**: True Positives / (True Positives + False Negatives).
- **Field F1 Score ($F_1$)**: $2 \cdot P \cdot R / (P + R)$.
- **Line-Item F1**: Harmonic mean of line item precision and recall, matching
  line items by normalized description and exact amount comparison.
- **Evidence Grounding Rate**:
  $$\text{Grounding Rate} = \frac{\text{Extracted Fields with Valid Page Evidence}}{\text{Total Extracted Fields}}$$

### 3. Verification & Decision Metrics
- **True Positive Rate (TPR / Recall)**: $\text{TP} / (\text{TP} + \text{FN})$.
- **False Negative Rate (FNR / Miss Rate)**: $\text{FN} / (\text{TP} + \text{FN})$.
  > [!IMPORTANT]
  > Because false negatives in invoice verification can lead to unreviewed fraudulent
  > or mismatched disbursements, the target FNR is strictly **0.00**.
- **Verdict Concordance (Accuracy)**: Proportion of documents where the derived
  verdict (`clear` vs `review_required`) exactly matches ground truth.

### 4. Explanation Guardrails
- **Guardrail Pass Rate**: Proportion of LLM provider drafts that pass safety
  guardrails without triggering deterministic fallback.
- **Numerical Contradiction Count**: Number of explanations introducing numbers
  unsupported by verification findings. Target: **0**.

### 5. Performance & Operational Metrics
- **Latency Percentiles**: $p_{50}$, $p_{95}$, and $p_{99}$ request durations.
- **Throughput**: Requests per second under bounded concurrency.

---

## Acceptance Thresholds

The preregistered acceptance thresholds for production readiness are:

| Metric Name | Criterion | Target Threshold | Rationale |
| --- | :---: | :---: | --- |
| `max_ocr_cer` | $\le$ | `0.05` (5%) | Ensures high-fidelity transcription for downstream extraction |
| `max_ocr_wer` | $\le$ | `0.15` (15%) | Tolerates minor punctuation variations while retaining semantic tokens |
| `min_extraction_f1` | $\ge$ | `0.90` (90%) | Requires near-complete factual header recovery |
| `min_line_item_f1` | $\ge$ | `0.85` (85%) | Accommodates line-item formatting complexity across vendors |
| `max_verification_fnr`| $\le$ | `0.00` (0%) | Hard safety floor: no undetected anomalies or mismatches |
| `min_verdict_accuracy`| $\ge$ | `0.95` (95%) | High concordance between system routing and expected disposition |
| `min_guardrail_pass_rate`| $\ge$ | `0.99` (99%) | Explanations must adhere strictly to numerical and factual evidence |
| `max_p95_latency_seconds`| $\le$ | `10.0s` | Bounds processing latency for interactive operator workflows |
| `min_slice_sample_count`| $\ge$ | `10` | Slices with $<10$ samples cannot certify unconditional GO |

---

## Uncertainty Quantification: Wilson Score Interval

For binomial proportions (precision, recall, accuracy, pass rate) evaluated on
sample size $n$ with observed successes $x$ and sample proportion $\hat{p} = x/n$,
confidence intervals are computed at the 95% confidence level ($z = 1.96$):

$$\text{Center} = \frac{\hat{p} + \frac{z^2}{2n}}{1 + \frac{z^2}{n}}, \quad
\text{Margin} = \frac{z}{1 + \frac{z^2}{n}} \sqrt{\frac{\hat{p}(1 - \hat{p})}{n} + \frac{z^2}{4n^2}}$$

Interval: $[\max(0, \text{Center} - \text{Margin}), \min(1, \text{Center} + \text{Margin})]$.

---

## Decision Framework

The automated evaluator (`veridoc-evaluate`) derives one of three outcomes:

1. **`GO`**:
   - All critical and non-critical acceptance thresholds satisfied.
   - All evaluated data slices meet the minimum sample size ($n \ge 10$).
   - No runtime or upstream artifact drift detected.
2. **`CONDITIONAL_GO`**:
   - All critical safety thresholds satisfied (`max_verification_fnr = 0.00`,
     `min_verdict_accuracy >= 0.95`).
   - Minor threshold breach (e.g. WER or latency) or one or more data slices
     have insufficient sample sizes.
   - Specific limitations, monitoring conditions, or sample expansion plans
     are documented.
3. **`NO_GO`**:
   - Any critical safety threshold fails (`verification_fnr > 0.00`,
     `verdict_accuracy < 0.95`, `extraction_f1 < 0.90`, or `guardrail_pass_rate < 0.99`).
   - Any slice with sufficient sample size fails critical safety thresholds.
   - Deployment is blocked pending remediation.

---

## Identity Capture & Drift Governance

Per ADR 0019, evaluations record:
- Application version (`veridoc.__version__`), Git commit hash, Python version, platform.
- Lockfile digest (`uv.lock` SHA-256).
- Tesseract binary version and language asset (`traineddata`) SHA-256 digests.
- Reference and review schema migration ledger versions.
- Model identifier, system prompt SHA-256, and JSON output schema SHA-256.

Any change to these identity records constitutes **drift**, requiring automated
flagging and re-evaluation before deploying subsequent releases.
