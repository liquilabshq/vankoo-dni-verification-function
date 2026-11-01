import httpx

from dni_verification.application.ports import DniRegistry
from dni_verification.application.services import VerifyDniService
from dni_verification.infrastructure.eldni_registry import EldniRegistry
from dni_verification.infrastructure.fake_registry import FakeDniRegistry
from dni_verification.infrastructure.settings import Settings


def build_registry(settings: Settings) -> DniRegistry:
    if settings.provider == "fake":
        return FakeDniRegistry()
    if settings.provider == "eldni":
        client = httpx.Client(timeout=settings.eldni_timeout_seconds, follow_redirects=True)
        return EldniRegistry(client, settings.eldni_base_url, settings.eldni_retries)
    raise ValueError(f"DNI_PROVIDER desconocido: {settings.provider!r} (usar 'eldni' o 'fake').")


def build_service(settings: Settings | None = None) -> VerifyDniService:
    return VerifyDniService(build_registry(settings or Settings.from_env()))
