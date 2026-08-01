"""FastAPI application setup for Veridoc."""

from fastapi import FastAPI

from veridoc import __version__

app = FastAPI(
    title="Veridoc",
    description="Invoice and purchase-order verification service.",
    version=__version__,
)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Return the service health status without touching external dependencies."""
    return {"status": "ok"}
