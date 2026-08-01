"""FastAPI application setup for Veridoc."""

from fastapi import FastAPI

from veridoc import __version__

app = FastAPI(
    title="Veridoc",
    description="Invoice and purchase-order verification service.",
    version=__version__,
)
