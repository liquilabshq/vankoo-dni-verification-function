import pytest

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
