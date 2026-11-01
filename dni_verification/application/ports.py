from typing import Protocol

from dni_verification.domain.dni import DniNumber
from dni_verification.domain.models import RegisteredName


class RegistryUnavailableError(Exception):
    """The source could not be queried or answered something unintelligible."""


class DniRegistry(Protocol):
    source: str

    def lookup(self, dni: DniNumber) -> RegisteredName | None:
        """The registered name, or None when the DNI does not exist.

        Raises RegistryUnavailableError when the answer cannot be trusted.
        """
        ...
