from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class VerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    NAME_MISMATCH = "NAME_MISMATCH"
    NOT_FOUND = "NOT_FOUND"


@dataclass(frozen=True)
class RegisteredName:
    """Name the registry holds for a DNI."""

    first_names: str
    paternal_surname: str
    maternal_surname: str


@dataclass(frozen=True)
class ProvidedName:
    """Name the investor declared in their profile."""

    first_name: str
    last_name: str


@dataclass(frozen=True)
class VerificationResult:
    dni: str
    status: VerificationStatus
    registered_name: RegisteredName | None
    source: str
    checked_at: datetime
