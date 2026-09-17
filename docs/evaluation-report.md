# Veridoc Evaluation and Production-Readiness Report: `eval-phase11-baseline-001`

## Decision: **CONDITIONAL GO (Remediation Required)**

> **Decision Rationale**: Approved conditionally. Conditions to remediate before general availability: Certain data slices have insufficient sample size.

### Artifact & Provider Identity

- **Application Version**: `0.1.0`
- **Git Commit**: `ddef4cb`
- **Python Version**: `3.12.12` (`win32`)
- **Lockfile SHA-256**: `5a09282ff1976077...`
- **Tesseract Version**: `5.3.0`
- **Reference DB Schema Version**: `4`
- **Review DB Schema Version**: `4`
- **Model**: `gpt-4o-mini`
- **Corpus Manifest**: `veridoc-synthetic-benchmark-v1` (version `1.0`, `3` documents)

### Preregistered Acceptance Thresholds

| Metric | Comparator | Threshold | Observed | Status |
| --- | :---: | :---: | :---: | :---: |
| `max_ocr_cer` | `<=` | `0.05` | `0.0097` | PASSED |
| `max_ocr_wer` | `<=` | `0.15` | `0.0375` | PASSED |
| `min_extraction_f1` | `>=` | `0.9` | `0.963` | PASSED |
| `min_line_item_f1` | `>=` | `0.85` | `0.9412` | PASSED |
| `max_verification_fnr` | `<=` | `0.0` | `0.0` | PASSED |
| `min_verdict_accuracy` | `>=` | `0.95` | `1.0` | PASSED |
| `min_guardrail_pass_rate` | `>=` | `0.99` | `1.0` | PASSED |
| `max_p95_latency_seconds` | `<=` | `10.0` | `2.15` | PASSED |

### Data Slices Performance Summary

| Dimension | Value | Samples | Min Sample Met? | OCR CER | Extraction F1 | Verification FNR | Verdict Accuracy |
| --- | --- | :---: | :---: | :---: | :---: | :---: | :---: |
| `language` | `eng` | 2 | No | `0.0050` | `1.0000` | `0.0000` | `1.0000` |
| `language` | `ara` | 1 | No | `0.0150` | `0.9200` | `0.0000` | `1.0000` |
| `quality` | `clean` | 2 | No | `0.0050` | `1.0000` | `0.0000` | `1.0000` |
| `quality` | `noisy` | 1 | No | `0.0150` | `0.9200` | `0.0000` | `1.0000` |
| `layout` | `standard` | 2 | No | `0.0050` | `1.0000` | `0.0000` | `1.0000` |
| `layout` | `dense` | 1 | No | `0.0150` | `0.9200` | `0.0000` | `1.0000` |

### Overall Component Metrics

- **OCR**: CER = `0.0097`, WER = `0.0375` (1850 chars, 320 words)
- **Extraction**: Precision = `0.9630`, Recall = `0.9630`, F1 = `0.9630`, Line-Item F1 = `0.9412`, Grounding Rate = `0.9630`
- **Verification**: Rules Evaluated = 42, TPR = `1.0000`, TNR = `1.0000`, FPR = `0.0000`, FNR = `0.0000`, Verdict Concordance = `1.0000`
- **Explanation**: Guardrail Pass Rate = `1.0000` (3 passes, 0 rejections), Fallback Invocations = 0, Numerical Contradictions = 0
- **Performance**: Requests = 3, p50 = `1.240s`, p95 = `2.150s`, p99 = `2.310s`, Throughput = `2.15 rps`

### Limitations & Exceptions

- Under-sampled slices requiring sample expansion: language=eng (sample_count=2 < 10), language=ara (sample_count=1 < 10), quality=clean (sample_count=2 < 10), quality=noisy (sample_count=1 < 10), layout=standard (sample_count=2 < 10), layout=dense (sample_count=1 < 10)

> **Report Expiration Date**: `2026-12-16` (Must re-evaluate before expiration)
