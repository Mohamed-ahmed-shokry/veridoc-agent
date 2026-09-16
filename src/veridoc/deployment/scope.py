"""Small ASGI scope helpers shared by middleware and application routes."""

from __future__ import annotations

from starlette.types import Scope


def route_relative_path(scope: Scope) -> str:
    """Return the route path without the configured root path."""
    path = str(scope.get("path", ""))
    root_path = str(scope.get("root_path", "")).rstrip("/")
    if root_path and path.startswith(f"{root_path}/"):
        path = path[len(root_path) :]
    return path.rstrip("/") or "/"


def client_host(scope: Scope) -> str:
    """Return a bounded client host key for per-client rate limiting."""
    client = scope.get("client")
    if isinstance(client, tuple) and client and isinstance(client[0], str):
        return client[0]
    return "<unknown>"


def is_loopback_host(host: str) -> bool:
    """Return whether the client host represents a loopback address."""
    if host in {"localhost", "testclient"}:
        return True
    try:
        import ipaddress

        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
