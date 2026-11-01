from collections.abc import Callable
from datetime import UTC, datetime

from dni_verification.application.ports import DniRegistry
from dni_verification.domain.dni import DniNumber
from dni_verification.domain.models import ProvidedName, VerificationResult, VerificationStatus
from dni_verification.domain.name_matcher import names_match


class VerifyDniService:
    def __init__(self, registry: DniRegistry, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._registry = registry
        self._clock = clock

    def verify(self, dni: DniNumber, provided: ProvidedName) -> VerificationResult:
        registered = self._registry.lookup(dni)

        if registered is None:
            status = VerificationStatus.NOT_FOUND
        elif names_match(provided, registered):
            status = VerificationStatus.VERIFIED
        else:
            status = VerificationStatus.NAME_MISMATCH

        return VerificationResult(
            dni=dni.value,
            status=status,
            registered_name=registered,
            source=self._registry.source,
            checked_at=self._clock(),
        )
