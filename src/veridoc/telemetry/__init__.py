"""Operational-only telemetry for the Phase 10 deployment profile.

This package exports aggregate counters, request records, and storage
figures restricted to the ``operational`` data class (ADR 0012, ADR 0017):
correlation IDs, static route templates, status codes, durations, and
aggregate resource figures. It never accepts or emits document bodies, OCR
text, extracted values, findings, credentials, tokens, temporary paths, or
provider payloads; every sink is covered by redaction tests. This package
must not import FastAPI, LangGraph, SQLite connection code, or vendor SDKs.
"""
