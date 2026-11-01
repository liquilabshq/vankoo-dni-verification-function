import re
from dataclasses import dataclass

_DNI_PATTERN = re.compile(r"[0-9]{8}")  # not \d: that also matches digits of other scripts


class InvalidDniError(ValueError):
    """The value is not an 8-digit Peruvian DNI."""


@dataclass(frozen=True)
class DniNumber:
    value: str

    def __post_init__(self) -> None:
        if not _DNI_PATTERN.fullmatch(self.value):
            raise InvalidDniError("El DNI debe tener exactamente 8 dígitos.")

    @property
    def masked(self) -> str:
        """Safe to log: the DNI is personal data (Ley 29733)."""
        return f"{self.value[:4]}****"
