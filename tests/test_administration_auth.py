"""Tests for local administration authentication policy."""

import secrets

import pytest

from veridoc.administration.auth import (
    AdminAuthenticationUnavailableError,
    AdminSettings,
    InvalidAdminCredentialsError,
    authorize_admin,
)

_TOKEN = "phase-8-fixture-token-000000000000"


def test_admin_settings_load_a_strong_token_without_repr_exposure() -> None:
    settings = AdminSettings.from_environment({"VERIDOC_ADMIN_TOKEN": _TOKEN})

    assert settings.token == _TOKEN
    assert _TOKEN not in repr(settings)


@pytest.mark.parametrize(
    "environment",
    [
        {},
        {"VERIDOC_ADMIN_TOKEN": "short"},
        {"VERIDOC_ADMIN_TOKEN": "x" * 31},
        {"VERIDOC_ADMIN_TOKEN": f"{'x' * 31}\n"},
        {"VERIDOC_ADMIN_TOKEN": "x" * 257},
    ],
)
def test_admin_settings_reject_missing_weak_or_unsafe_tokens(
    environment: dict[str, str],
) -> None:
    with pytest.raises(AdminAuthenticationUnavailableError):
        AdminSettings.from_environment(environment)


def test_authorize_admin_accepts_the_exact_bearer_token() -> None:
    settings = AdminSettings(token=_TOKEN)

    authorize_admin(f"Bearer {_TOKEN}", settings)


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "",
        _TOKEN,
        f"Basic {_TOKEN}",
        "Bearer wrong-token",
        f"Bearer  {_TOKEN}",
    ],
)
def test_authorize_admin_returns_one_generic_error_for_invalid_credentials(
    authorization: str | None,
) -> None:
    settings = AdminSettings(token=_TOKEN)

    with pytest.raises(InvalidAdminCredentialsError) as raised:
        authorize_admin(authorization, settings)

    assert raised.value.code == "invalid_admin_credentials"
    assert _TOKEN not in str(raised.value)


def test_authorize_admin_compares_even_malformed_credentials_in_constant_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compared: list[tuple[bytes, bytes]] = []

    def compare(left: bytes, right: bytes) -> bool:
        compared.append((left, right))
        return False

    monkeypatch.setattr(secrets, "compare_digest", compare)

    with pytest.raises(InvalidAdminCredentialsError):
        authorize_admin("Basic malformed", AdminSettings(token=_TOKEN))

    assert len(compared) == 1
    assert len(compared[0][0]) == len(compared[0][1]) == 32
