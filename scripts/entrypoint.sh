#!/bin/sh
set -eu

# Read mounted container secrets into process environment if not already set (ADR 0014)
if [ -z "${OPENAI_API_KEY:-}" ] && [ -f "/secrets/OPENAI_API_KEY" ]; then
    OPENAI_API_KEY="$(cat /secrets/OPENAI_API_KEY)"
    export OPENAI_API_KEY
fi

if [ -z "${VERIDOC_ADMIN_TOKEN:-}" ] && [ -f "/secrets/VERIDOC_ADMIN_TOKEN" ]; then
    VERIDOC_ADMIN_TOKEN="$(cat /secrets/VERIDOC_ADMIN_TOKEN)"
    export VERIDOC_ADMIN_TOKEN
fi

if [ -z "${VERIDOC_REVIEW_ACTORS_FILE:-}" ] && [ -f "/secrets/actors.json" ]; then
    VERIDOC_REVIEW_ACTORS_FILE="/secrets/actors.json"
    export VERIDOC_REVIEW_ACTORS_FILE
fi

exec "$@"
