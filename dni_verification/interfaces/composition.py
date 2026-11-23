import httpx

from dni_verification.application.ports import DniRegistry
from dni_verification.application.services import VerifyDniService
from dni_verification.infrastructure.apiperu_registry import ApiPeruRegistry
from dni_verification.infrastructure.eldni_registry import EldniRegistry
from dni_verification.infrastructure.fake_registry import FakeDniRegistry
from dni_verification.infrastructure.settings import Settings


def build_registry(settings: Settings) -> DniRegistry:
    if settings.provider == "fake":
        return FakeDniRegistry()
    if settings.provider == "eldni":
        client = httpx.Client(timeout=settings.eldni_timeout_seconds, follow_redirects=True)
        return EldniRegistry(client, settings.eldni_base_url, settings.eldni_retries)
    if settings.provider == "apiperu":
        if not settings.apiperu_token:
            # Se falla al arrancar y no en la primera consulta: una configuración incompleta debe verse ya.
            raise ValueError("APIPERU_TOKEN es obligatorio cuando DNI_PROVIDER=apiperu.")
        client = httpx.Client(timeout=settings.apiperu_timeout_seconds)
        return ApiPeruRegistry(client, settings.apiperu_token, settings.apiperu_base_url, settings.apiperu_retries)
    raise ValueError(f"DNI_PROVIDER desconocido: {settings.provider!r} (usar 'eldni', 'apiperu' o 'fake').")


def build_service(settings: Settings | None = None) -> VerifyDniService:
    return VerifyDniService(build_registry(settings or Settings.from_env()))
