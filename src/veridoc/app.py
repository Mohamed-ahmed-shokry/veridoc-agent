"""FastAPI application setup for Veridoc."""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from veridoc import __version__


class HealthResponse(BaseModel):
    """Typed response returned by the service health check."""

    status: Literal["ok"] = "ok"


app = FastAPI(
    title="Veridoc",
    description="Invoice and purchase-order verification service.",
    version=__version__,
)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Return the service health status without touching external dependencies."""
    return {"status": "ok"}
