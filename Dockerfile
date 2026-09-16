# Veridoc Deployment Container Image (Phase 10, ADR 0011)
FROM python:3.12.12-slim-bookworm AS runtime

# Install system dependencies: Tesseract OCR with English and Arabic language data
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-ara \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root runtime group and user
RUN groupadd -g 10001 veridoc && \
    useradd -u 10001 -g veridoc -s /usr/sbin/nologin -d /app -M veridoc

# Install uv for reproducible locked dependency synchronization
COPY --from=ghcr.io/astral-sh/uv:0.9.13 /uv /bin/uv

WORKDIR /app

# Copy dependency lockfile and metadata
COPY pyproject.toml uv.lock README.md ./

# Synchronize production dependencies
RUN uv sync --no-dev --locked --no-install-project

# Copy application source
COPY src/ /app/src/

# Install the project into the locked environment
RUN uv sync --no-dev --locked

# Prepare mount points for SQLite stores, quarantine, and runtime secrets
RUN mkdir -p /data /secrets && \
    chown -R veridoc:veridoc /data /secrets /app

# Copy container entrypoint script
COPY scripts/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Switch to non-root user
USER veridoc:veridoc

# Environment configuration for single-writer SQLite and Tesseract
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VERIDOC_REFERENCE_DATABASE="/data/veridoc-reference.sqlite3" \
    VERIDOC_REVIEW_DATABASE="/data/veridoc-review.sqlite3" \
    VERIDOC_QUARANTINE_DIR="/data/quarantine" \
    TESSDATA_PREFIX="/usr/share/tesseract-ocr/5/tessdata" \
    TESSERACT_LANG="eng+ara"

EXPOSE 8000

ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]
CMD ["uvicorn", "veridoc.app:app", "--host", "0.0.0.0", "--port", "8000"]
