"""Authentication policy for local reference-data administration."""

from __future__ import annotations

import os
import re
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field

_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9._~+/=-]{32,256}$")


class AdminAuthenticationUnavailableError(RuntimeError):
    """Raised when the server lacks valid administration credentials."""

    code = "admin_authentication_unavailable"
    message = "Reference-data administration is not available on this server."

    def __init__(self) -> None:
        super().__init__(self.message)


class InvalidAdminCredentialsError(RuntimeError):
    """Raised for every missing, malformed, or incorrect bearer credential."""

    code = "invalid_admin_credentials"
    message = "Administrative credentials are invalid."

    def __init__(self) -> None:
        super().__init__(self.message)


@dataclass(frozen=True, slots=True)
class AdminSettings:
    """Validated local administration authentication settings."""

    token: str = field(repr=False)

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> AdminSettings:
        """Load one strong bearer token without exposing it in errors."""
        values = os.environ if environment is None else environment
        token = values.get("VERIDOC_ADMIN_TOKEN", "")
        if not _TOKEN_PATTERN.fullmatch(token):
            raise AdminAuthenticationUnavailableError
        return cls(token=token)


def authorize_admin(authorization: str | None, settings: AdminSettings) -> None:
    """Require one constant-time matched bearer credential."""
    scheme, separator, candidate = (authorization or "").partition(" ")
    well_formed = separator == " " and scheme.lower() == "bearer"
    matches = secrets.compare_digest(candidate, settings.token)
    if not well_formed or not matches:
        raise InvalidAdminCredentialsError
