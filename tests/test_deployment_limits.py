"""Deployment limits tests: bounded concurrency and per-client rate limiting."""

import asyncio

import httpx
import pytest

from veridoc.app import app
from veridoc.deployment.limits import (
    LimitsConfigurationError,
    LimitsSettings,
    TokenBucket,
)


def test_limits_settings_defaults_to_unlimited() -> None:
    """Empty environment yields disabled limits."""
    settings = LimitsSettings.from_environment({})
    assert settings.max_concurrency == 0
    assert settings.rate_limit_capacity == 0.0
    assert settings.rate_limit_refill_per_second == 0.0


def test_limits_settings_parses_nonnegative_integers() -> None:
    """Nonnegative integers are accepted for concurrency."""
    settings = LimitsSettings.from_environment({"VERIDOC_MAX_CONCURRENCY": "4"})
    assert settings.max_concurrency == 4


def test_limits_settings_parses_nonnegative_floats() -> None:
    """Nonnegative floats are accepted for rate-limit parameters."""
    settings = LimitsSettings.from_environment(
        {
            "VERIDOC_RATE_LIMIT_CAPACITY": "10.5",
            "VERIDOC_RATE_LIMIT_REFILL_PER_SECOND": "2.0",
        }
    )
    assert settings.rate_limit_capacity == 10.5
    assert settings.rate_limit_refill_per_second == 2.0


def test_limits_settings_rejects_negative_concurrency() -> None:
    """Negative concurrency raises the configuration error."""
    with pytest.raises(LimitsConfigurationError):
        LimitsSettings.from_environment({"VERIDOC_MAX_CONCURRENCY": "-1"})


def test_limits_settings_rejects_negative_rate_capacity() -> None:
    """Negative rate capacity raises the configuration error."""
    with pytest.raises(LimitsConfigurationError):
        LimitsSettings.from_environment({"VERIDOC_RATE_LIMIT_CAPACITY": "-5"})


def test_limits_settings_rejects_negative_refill() -> None:
    """Negative refill rate raises the configuration error."""
    with pytest.raises(LimitsConfigurationError):
        LimitsSettings.from_environment(
            {"VERIDOC_RATE_LIMIT_REFILL_PER_SECOND": "-0.1"}
        )


def test_limits_settings_rejects_nonnumeric_concurrency() -> None:
    """Non-numeric concurrency raises the configuration error."""
    with pytest.raises(LimitsConfigurationError):
        LimitsSettings.from_environment({"VERIDOC_MAX_CONCURRENCY": "not-an-int"})


def test_limits_settings_rejects_nonnumeric_rate_capacity() -> None:
    """Non-numeric rate capacity raises the configuration error."""
    with pytest.raises(LimitsConfigurationError):
        LimitsSettings.from_environment({"VERIDOC_RATE_LIMIT_CAPACITY": "not-a-float"})


def test_limits_settings_rejects_nonnumeric_refill() -> None:
    """Non-numeric refill rate raises the configuration error."""
    with pytest.raises(LimitsConfigurationError):
        LimitsSettings.from_environment({"VERIDOC_RATE_LIMIT_REFILL_PER_SECOND": "bad"})


def test_limits_settings_rejects_nan_and_infinity() -> None:
    """NaN and infinity are rejected for float parameters."""
    with pytest.raises(LimitsConfigurationError):
        LimitsSettings.from_environment({"VERIDOC_RATE_LIMIT_CAPACITY": "nan"})
    with pytest.raises(LimitsConfigurationError):
        LimitsSettings.from_environment({"VERIDOC_RATE_LIMIT_REFILL_PER_SECOND": "inf"})


def test_token_bucket_exhausts_at_capacity() -> None:
    """A bucket with no refill refuses after `capacity` takes."""
    bucket = TokenBucket(capacity=3, refill_per_second=0.0)
    assert bucket.take() is True
    assert bucket.take() is True
    assert bucket.take() is True
    assert bucket.take() is False


def test_token_bucket_refills_over_time() -> None:
    """A bucket refills tokens after the configured interval."""
    # clock is called once in __init__ (t=0), then once per take()
    times = [0.0, 0.0, 0.0, 0.5, 0.5, 1.0, 1.0, 1.5, 1.5]
    clock_iter = iter(times)
    bucket = TokenBucket(
        capacity=2, refill_per_second=2.0, clock=lambda: next(clock_iter)
    )
    assert bucket.take() is True  # t=0.0: tokens=2→1
    assert bucket.take() is True  # t=0.0: tokens=1→0
    assert bucket.take() is True  # t=0.5: tokens=0→refill 1→0 (elapsed 0.5s * 2/s = 1)
    assert bucket.take() is False  # t=0.5: tokens=0, no refill
    # advance by another 0.5s → +1 token
    assert bucket.take() is True  # t=1.0: tokens=0→refill 1→0
    assert bucket.take() is False  # t=1.0: tokens=0
    # advance by another 0.5s → +1 token
    assert bucket.take() is True  # t=1.5: tokens=0→refill 1→0
    assert bucket.take() is False  # t=1.5: tokens=0


def test_token_bucket_caps_at_capacity() -> None:
    """Tokens never exceed the configured capacity."""
    # clock: init(t=0), 6 takes at t=0, then 6 takes at t=10
    times = [0.0] + [0.0] * 6 + [10.0] * 6
    clock_iter = iter(times)
    bucket = TokenBucket(
        capacity=5, refill_per_second=10.0, clock=lambda: next(clock_iter)
    )
    # consume all 5 at t=0
    for _ in range(5):
        assert bucket.take() is True
    assert bucket.take() is False
    # huge elapsed → refill caps at capacity, not 5 + 100
    for _ in range(5):
        assert bucket.take() is True
    assert bucket.take() is False


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


def _client_with_host(host: str) -> httpx.AsyncClient:
    """Return an ASGI client whose scope reports the given client host."""
    transport = httpx.ASGITransport(app=app, client=(host, 12345))
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.anyio
async def test_health_ready_and_metrics_bypass_all_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Operational probes are never rate-limited or concurrency-limited."""
    monkeypatch.setenv("VERIDOC_MAX_CONCURRENCY", "1")
    monkeypatch.setenv("VERIDOC_RATE_LIMIT_CAPACITY", "1")
    monkeypatch.setenv("VERIDOC_RATE_LIMIT_REFILL_PER_SECOND", "0")
    for name in (
        "OPENAI_API_KEY",
        "VERIDOC_LLM_MODEL",
        "VERIDOC_REVIEW_ACTORS_FILE",
        "VERIDOC_REVIEW_ORIGIN",
        "VERIDOC_REFERENCE_DATABASE",
        "VERIDOC_REVIEW_DATABASE",
    ):
        monkeypatch.delenv(name, raising=False)

    from veridoc.deployment.limits import (
        BoundedConcurrencyMiddleware,
        RateLimitMiddleware,
    )

    wrapped = BoundedConcurrencyMiddleware(RateLimitMiddleware(app))
    transport = httpx.ASGITransport(app=wrapped, client=("10.9.9.9", 1))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/missing-probe-target")).status_code == 404
        assert (await client.get("/health")).status_code == 200
        assert (await client.get("/ready")).status_code == 200
        # the single rate token is spent: a normal route now fails ...
        assert (await client.get("/missing-probe-target")).status_code == 429
        # ... while both probes keep succeeding through the same stack.
        assert (await client.get("/health")).status_code == 200
        assert (await client.get("/ready")).status_code == 200


@pytest.mark.anyio
async def test_concurrency_middleware_caps_in_flight_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A concurrency limit of 1 serializes three concurrent sleepers."""
    monkeypatch.setenv("VERIDOC_MAX_CONCURRENCY", "1")
    monkeypatch.delenv("VERIDOC_RATE_LIMIT_CAPACITY", raising=False)
    monkeypatch.delenv("VERIDOC_RATE_LIMIT_REFILL_PER_SECOND", raising=False)

    active = 0
    max_seen = 0
    done = asyncio.Event()

    async def sleep_route(_: httpx.AsyncClient) -> None:
        nonlocal active, max_seen
        active += 1
        max_seen = max(max_seen, active)
        try:
            await asyncio.sleep(0.05)
        finally:
            active -= 1
            if active == 0:
                done.set()

    # We can't easily add a test route to the live app. Instead, test the
    # middleware directly by wrapping a synthetic ASGI app.
    from veridoc.deployment.limits import BoundedConcurrencyMiddleware

    async def inner_app(scope, receive, send):
        if scope["type"] == "http" and scope["path"] == "/test":
            await sleep_route(None)
            await _send_ok(scope, receive, send)
        else:
            await _send_not_found(scope, receive, send)

    middleware = BoundedConcurrencyMiddleware(inner_app)
    transport = httpx.ASGITransport(app=middleware, client=("127.0.0.1", 1))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await asyncio.gather(
            client.get("/test"),
            client.get("/test"),
            client.get("/test"),
        )
    await asyncio.wait_for(done.wait(), timeout=2.0)
    assert max_seen == 1


@pytest.mark.anyio
async def test_rate_limit_middleware_returns_429_when_bucket_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Capacity 2, refill 0: third request to same host gets 429."""
    monkeypatch.setenv("VERIDOC_RATE_LIMIT_CAPACITY", "2")
    monkeypatch.setenv("VERIDOC_RATE_LIMIT_REFILL_PER_SECOND", "0")
    monkeypatch.delenv("VERIDOC_MAX_CONCURRENCY", raising=False)

    from veridoc.deployment.limits import RateLimitMiddleware

    async def inner_app(scope, receive, send):
        if scope["type"] == "http" and scope["path"] == "/test":
            await _send_ok(scope, receive, send)
        else:
            await _send_not_found(scope, receive, send)

    middleware = RateLimitMiddleware(inner_app)
    transport = httpx.ASGITransport(app=middleware, client=("10.0.0.1", 1))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.get("/test")
        r2 = await client.get("/test")
        r3 = await client.get("/test")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    assert r3.json()["detail"]["code"] == "rate_limit_exceeded"


@pytest.mark.anyio
async def test_rate_limit_middleware_uses_per_host_buckets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Different hosts have independent token buckets."""
    monkeypatch.setenv("VERIDOC_RATE_LIMIT_CAPACITY", "1")
    monkeypatch.setenv("VERIDOC_RATE_LIMIT_REFILL_PER_SECOND", "0")
    monkeypatch.delenv("VERIDOC_MAX_CONCURRENCY", raising=False)

    from veridoc.deployment.limits import RateLimitMiddleware

    async def inner_app(scope, receive, send):
        if scope["type"] == "http" and scope["path"] == "/test":
            await _send_ok(scope, receive, send)
        else:
            await _send_not_found(scope, receive, send)

    middleware = RateLimitMiddleware(inner_app)

    async with (
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=middleware, client=("10.0.0.1", 1)),
            base_url="http://test",
        ) as c1,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=middleware, client=("10.0.0.2", 1)),
            base_url="http://test",
        ) as c2,
    ):
        r1 = await c1.get("/test")
        r2 = await c2.get("/test")
        r3 = await c1.get("/test")
        r4 = await c2.get("/test")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    assert r4.status_code == 429


@pytest.mark.anyio
async def test_limits_config_error_maps_to_safe_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid limit config produces a safe 503 on the affected route."""
    monkeypatch.setenv("VERIDOC_MAX_CONCURRENCY", "-1")

    from veridoc.deployment.limits import BoundedConcurrencyMiddleware

    async def inner_app(scope, receive, send):
        if scope["type"] == "http" and scope["path"] == "/test":
            await _send_ok(scope, receive, send)
        else:
            await _send_not_found(scope, receive, send)

    middleware = BoundedConcurrencyMiddleware(inner_app)
    transport = httpx.ASGITransport(app=middleware, client=("127.0.0.1", 1))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/test")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "deployment_limits_unavailable"


async def _send_ok(scope, receive, send):
    from starlette.responses import PlainTextResponse

    await PlainTextResponse("ok")(scope, receive, send)


async def _send_not_found(scope, receive, send):
    from starlette.responses import PlainTextResponse

    await PlainTextResponse("not found", status_code=404)(scope, receive, send)
