"""Operational deployment surface for the Phase 10 container profile.

This package owns local, deterministic readiness signals, bounded request
concurrency, rate limiting, and operational telemetry. It must not import
FastAPI, LangGraph, SQLite connection code, or vendor SDKs.
"""
