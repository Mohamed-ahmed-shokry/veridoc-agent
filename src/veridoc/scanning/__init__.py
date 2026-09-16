"""Upload malware-scanning boundary for the Phase 10 deployment profile.

Every document route scans its validated bytes before they reach a decoder,
OCR engine, provider payload, or persistent store (ADR 0016). The scanning
boundary fails closed: a positive or a scanner failure maps to a typed safe
error and the bytes never continue toward decoding. This package must not
import FastAPI, LangGraph, SQLite connection code, or vendor SDKs.
"""
