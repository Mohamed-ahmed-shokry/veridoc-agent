# Architecture Decision Records

This directory contains records for meaningful Veridoc architecture decisions.
Use sequential four-digit names such as `0001-use-tesseract-for-v1.md`.

Each record must include:

- title
- status
- context
- decision
- alternatives considered
- consequences

Create an ADR only when a decision materially constrains later implementation.
Do not use ADRs for routine code-level choices.

Accepted decisions:

- [0001: Use Tesseract for the version 1 OCR baseline](0001-use-tesseract-for-v1.md)
- [0002: Use the OpenAI Responses API for Phase 2 extraction](0002-use-openai-responses-for-phase-2.md)
- [0003: Use SQLite for Phase 3 reference data](0003-use-sqlite-for-phase-3-reference-data.md)
- [0004: Use validated LLM proposals for explanations](0004-use-validated-llm-proposals-for-explanations.md)
- [0005: Use review-required processing verdicts](0005-use-review-required-processing-verdicts.md)
- [0006: Use a bearer token for local administration](0006-use-bearer-token-for-local-administration.md)
- [0007: Use forward-only SQLite migrations](0007-use-forward-only-sqlite-migrations.md)
