from dni_verification.application.ports import RegistryUnavailableError
from dni_verification.domain.dni import DniNumber
from dni_verification.domain.models import RegisteredName

# DNIs made up for demos and local tests; none belongs to a real person.
DEMO_RECORDS: dict[str, RegisteredName] = {
    "12345678": RegisteredName("JUAN CARLOS", "PEREZ", "GOMEZ"),
    "87654321": RegisteredName("MARIA ELENA", "QUISPE", "HUAMAN"),
}

# Makes the fake behave as if the source were down, to exercise the 502 path.
UNAVAILABLE_DNI = "00000503"


class FakeDniRegistry:
    source = "fake"

    def __init__(self, records: dict[str, RegisteredName] | None = None) -> None:
        self._records = DEMO_RECORDS if records is None else records

    def lookup(self, dni: DniNumber) -> RegisteredName | None:
        if dni.value == UNAVAILABLE_DNI:
            raise RegistryUnavailableError("Fuente simulada no disponible.")
        return self._records.get(dni.value)
