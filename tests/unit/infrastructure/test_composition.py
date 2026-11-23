import pytest

from dni_verification.infrastructure.apiperu_registry import ApiPeruRegistry
from dni_verification.infrastructure.eldni_registry import EldniRegistry
from dni_verification.infrastructure.fake_registry import FakeDniRegistry
from dni_verification.infrastructure.settings import Settings
from dni_verification.interfaces.composition import build_registry


def test_defaults_to_eldni() -> None:
    assert isinstance(build_registry(Settings()), EldniRegistry)


def test_fake_provider() -> None:
    assert isinstance(build_registry(Settings(provider="fake")), FakeDniRegistry)


def test_unknown_provider_fails_fast() -> None:
    with pytest.raises(ValueError, match="DNI_PROVIDER"):
        build_registry(Settings(provider="reniec"))


def test_settings_are_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DNI_PROVIDER", "FAKE")
    monkeypatch.setenv("ELDNI_BASE_URL", "http://localhost:9999/")
    monkeypatch.setenv("ELDNI_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("ELDNI_RETRIES", "3")

    settings = Settings.from_env()

    assert settings == Settings(
        provider="fake", eldni_base_url="http://localhost:9999", eldni_timeout_seconds=2.5, eldni_retries=3
    )


def test_apiperu_provider_needs_a_token() -> None:
    with pytest.raises(ValueError, match="APIPERU_TOKEN"):
        build_registry(Settings(provider="apiperu"))


def test_apiperu_provider_with_a_token() -> None:
    assert isinstance(build_registry(Settings(provider="apiperu", apiperu_token="t")), ApiPeruRegistry)


def test_the_token_never_shows_in_the_settings_repr() -> None:
    assert "secreto-unico" not in repr(Settings(provider="apiperu", apiperu_token="secreto-unico"))


def test_apiperu_settings_are_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DNI_PROVIDER", "apiperu")
    monkeypatch.setenv("APIPERU_TOKEN", "  t-123  ")
    monkeypatch.setenv("APIPERU_BASE_URL", "http://localhost:9/")
    monkeypatch.setenv("APIPERU_TIMEOUT_SECONDS", "3")
    monkeypatch.setenv("APIPERU_RETRIES", "0")

    settings = Settings.from_env()

    assert settings.provider == "apiperu"
    assert settings.apiperu_token == "t-123"
    assert settings.apiperu_base_url == "http://localhost:9"
    assert settings.apiperu_timeout_seconds == 3.0
    assert settings.apiperu_retries == 0
