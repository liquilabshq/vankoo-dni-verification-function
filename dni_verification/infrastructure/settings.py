import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    provider: str = "eldni"
    eldni_base_url: str = "https://eldni.com"
    eldni_timeout_seconds: float = 8.0
    eldni_retries: int = 1

    @classmethod
    def from_env(cls) -> "Settings":
        defaults = cls()
        return cls(
            provider=os.environ.get("DNI_PROVIDER", defaults.provider).lower(),
            eldni_base_url=os.environ.get("ELDNI_BASE_URL", defaults.eldni_base_url).rstrip("/"),
            eldni_timeout_seconds=float(os.environ.get("ELDNI_TIMEOUT_SECONDS", defaults.eldni_timeout_seconds)),
            eldni_retries=int(os.environ.get("ELDNI_RETRIES", defaults.eldni_retries)),
        )
