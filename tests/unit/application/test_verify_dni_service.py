from datetime import UTC, datetime

import pytest

from dni_verification.application.ports import RegistryUnavailableError
from dni_verification.application.services import VerifyDniService
from dni_verification.domain.dni import DniNumber
from dni_verification.domain.models import ProvidedName, RegisteredName, VerificationStatus
from dni_verification.infrastructure.fake_registry import FakeDniRegistry

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
RECORDS = {"12345678": RegisteredName("JUAN CARLOS", "PEREZ", "GOMEZ")}


def make_service() -> VerifyDniService:
    return VerifyDniService(FakeDniRegistry(RECORDS), clock=lambda: NOW)


def test_verified_when_the_dni_exists_and_the_name_matches() -> None:
    result = make_service().verify(DniNumber("12345678"), ProvidedName("Juan Carlos", "Perez Gomez"))

    assert result.status is VerificationStatus.VERIFIED
    assert result.registered_name == RECORDS["12345678"]
    assert result.source == "fake"
    assert result.checked_at == NOW


def test_name_mismatch_when_the_dni_belongs_to_someone_else() -> None:
    result = make_service().verify(DniNumber("12345678"), ProvidedName("Pedro", "Ramos"))

    assert result.status is VerificationStatus.NAME_MISMATCH
    assert result.registered_name == RECORDS["12345678"]


def test_not_found_when_the_registry_does_not_know_the_dni() -> None:
    result = make_service().verify(DniNumber("11111111"), ProvidedName("Juan", "Perez"))

    assert result.status is VerificationStatus.NOT_FOUND
    assert result.registered_name is None


def test_registry_failures_are_not_swallowed() -> None:
    with pytest.raises(RegistryUnavailableError):
        make_service().verify(DniNumber("00000503"), ProvidedName("Juan", "Perez"))
