import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    provider: str = "eldni"
    eldni_base_url: str = "https://eldni.com"
    eldni_timeout_seconds: float = 8.0
    eldni_retries: int = 1
    apiperu_base_url: str = "https://api.apiperu.pe"
    # repr=False: el token nunca debe salir en un log ni en un traceback que imprima la configuración.
    apiperu_token: str = field(default="", repr=False)
    apiperu_timeout_seconds: float = 8.0
    apiperu_retries: int = 1

    @classmethod
    def from_env(cls) -> "Settings":
        defaults = cls()
        return cls(
            provider=os.environ.get("DNI_PROVIDER", defaults.provider).lower(),
            eldni_base_url=os.environ.get("ELDNI_BASE_URL", defaults.eldni_base_url).rstrip("/"),
            eldni_timeout_seconds=float(os.environ.get("ELDNI_TIMEOUT_SECONDS", defaults.eldni_timeout_seconds)),
            eldni_retries=int(os.environ.get("ELDNI_RETRIES", defaults.eldni_retries)),
            apiperu_base_url=os.environ.get("APIPERU_BASE_URL", defaults.apiperu_base_url).rstrip("/"),
            apiperu_token=os.environ.get("APIPERU_TOKEN", defaults.apiperu_token).strip(),
            apiperu_timeout_seconds=float(os.environ.get("APIPERU_TIMEOUT_SECONDS", defaults.apiperu_timeout_seconds)),
            apiperu_retries=int(os.environ.get("APIPERU_RETRIES", defaults.apiperu_retries)),
        )
