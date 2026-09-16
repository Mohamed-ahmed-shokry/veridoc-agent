"""Bounded request concurrency and per-client rate limiting.

Phase 10 places both controls at the ASGI boundary so they apply to every
route without coupling the processing domains to quota logic. Both limits
are disabled by default so the local development workflow is unchanged, and
the container profile enables them through process environment variables.
Limiting is a deployment concern; this module must not import FastAPI,
LangGraph, SQLite connection code, or vendor SDKs.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from math import isfinite

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from veridoc.deployment.scope import client_host, route_relative_path
from veridoc.telemetry.registry import REGISTRY

_LIMIT_EXEMPT_PATHS = frozenset({"/health", "/ready", "/metrics"})
_MAX_TRACKED_CLIENTS = 1024


class LimitsConfigurationError(RuntimeError):
    """Raised when the configured deployment limits are invalid."""

    code = "deployment_limits_unavailable"
    message = "Deployment limits are not available on this server."

    def __init__(self) -> None:
        super().__init__(self.message)


@dataclass(frozen=True, slots=True)
class LimitsSettings:
    """Loadable request-limit configuration read from the process environment."""

    max_concurrency: int = 0
    rate_limit_capacity: float = 0.0
    rate_limit_refill_per_second: float = 0.0

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> LimitsSettings:
        """Load nonnegative limit values, rejecting malformed configuration."""
        values = os.environ if environment is None else environment
        return cls(
            max_concurrency=_bounded_int(
                values.get("VERIDOC_MAX_CONCURRENCY"), default=0
            ),
            rate_limit_capacity=_bounded_float(
                values.get("VERIDOC_RATE_LIMIT_CAPACITY"), default=0.0
            ),
            rate_limit_refill_per_second=_bounded_float(
                values.get("VERIDOC_RATE_LIMIT_REFILL_PER_SECOND"), default=0.0
            ),
        )


class TokenBucket:
    """A small monotonic-clock token bucket for per-client rate limiting."""

    def __init__(
        self,
        capacity: float,
        refill_per_second: float,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._capacity = capacity
        self._refill_per_second = refill_per_second
        self._clock = clock if clock is not None else time.monotonic
        self._tokens = capacity
        self._updated_at = float(self._clock())

    def take(self) -> bool:
        """Consume one token when available; return False when exhausted."""
        now = float(self._clock())
        elapsed = now - self._updated_at
        self._tokens = min(
            self._capacity, self._tokens + elapsed * self._refill_per_second
        )
        self._updated_at = now
        if self._tokens < 1.0:
            return False
        self._tokens -= 1.0
        return True


class BoundedConcurrencyMiddleware:
    """Cap the number of simultaneously in-flight HTTP requests.

    Requests beyond the configured concurrency limit wait for an in-flight
    slot instead of failing; the queue is bounded by the event loop and the
    operator-provided worker backlog. Health and readiness probes bypass the
    limit so operators always retain a liveness signal.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app
        self._settings: LimitsSettings | None = None
        self._semaphore: asyncio.Semaphore | None = None

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        if route_relative_path(scope) in _LIMIT_EXEMPT_PATHS:
            await self._app(scope, receive, send)
            return
        try:
            settings = LimitsSettings.from_environment()
        except LimitsConfigurationError:
            await _send_limits_unavailable(scope, receive, send)
            return
        if settings.max_concurrency <= 0:
            await self._app(scope, receive, send)
            return
        semaphore = self._semaphore_for(settings)
        async with semaphore:
            await self._app(scope, receive, send)

    def _semaphore_for(self, settings: LimitsSettings) -> asyncio.Semaphore:
        if (
            self._settings is not None
            and self._semaphore is not None
            and self._settings == settings
        ):
            return self._semaphore
        self._settings = settings
        self._semaphore = asyncio.Semaphore(settings.max_concurrency)
        return self._semaphore


class RateLimitMiddleware:
    """Reject one request per client once its token bucket is exhausted.

    Clients are keyed by source host. In the Phase 10 proxy topology every
    remote browser shares the loopback-proxy host, so the bucket throttles
    the proxy as a whole; per-remote-client identity is a later concern.
    Buckets for idle clients are pruned when the tracked set grows large.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app
        self._buckets: dict[str, TokenBucket] = {}

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        if route_relative_path(scope) in _LIMIT_EXEMPT_PATHS:
            await self._app(scope, receive, send)
            return
        try:
            settings = LimitsSettings.from_environment()
        except LimitsConfigurationError:
            await _send_limits_unavailable(scope, receive, send)
            return
        if settings.rate_limit_capacity <= 0:
            await self._app(scope, receive, send)
            return
        host = client_host(scope)
        bucket = self._buckets.get(host)
        if bucket is None:
            if len(self._buckets) >= _MAX_TRACKED_CLIENTS:
                self._prune_idle_buckets()
            bucket = TokenBucket(
                settings.rate_limit_capacity,
                settings.rate_limit_refill_per_second,
            )
            self._buckets[host] = bucket
        if not bucket.take():
            REGISTRY.record_rate_limited()
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": {
                        "code": "rate_limit_exceeded",
                        "message": "Too many requests.",
                    }
                },
            )
            await response(scope, receive, send)
            return
        await self._app(scope, receive, send)

    def _prune_idle_buckets(self) -> None:
        if len(self._buckets) < _MAX_TRACKED_CLIENTS:
            return
        for host in list(self._buckets)[: _MAX_TRACKED_CLIENTS // 4]:
            self._buckets.pop(host, None)


async def _send_limits_unavailable(scope: Scope, receive: Receive, send: Send) -> None:
    response = JSONResponse(
        status_code=503,
        content={
            "detail": {
                "code": LimitsConfigurationError.code,
                "message": LimitsConfigurationError.message,
            }
        },
    )
    await response(scope, receive, send)


def _bounded_int(raw_value: str | None, *, default: int) -> int:
    if raw_value is None or not raw_value.strip():
        return default
    try:
        parsed = int(raw_value)
    except ValueError:
        raise LimitsConfigurationError from None
    if parsed < 0:
        raise LimitsConfigurationError
    return parsed


def _bounded_float(raw_value: str | None, *, default: float) -> float:
    if raw_value is None or not raw_value.strip():
        return default
    try:
        parsed = float(raw_value)
    except ValueError:
        raise LimitsConfigurationError from None
    if not isfinite(parsed) or parsed < 0:
        raise LimitsConfigurationError
    return parsed
