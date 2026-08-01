"""Command-line entry point for running the Veridoc API."""

import uvicorn


def main() -> None:
    """Start the local Veridoc API server."""
    uvicorn.run("veridoc.app:app", host="127.0.0.1", port=8000)
