import pytest

from dni_verification.domain.models import ProvidedName, RegisteredName
from dni_verification.domain.name_matcher import names_match

REGISTERED = RegisteredName("JUAN CARLOS", "PEREZ", "GOMEZ")


@pytest.mark.parametrize(
    ("first", "last"),
    [
        ("JUAN CARLOS", "PEREZ GOMEZ"),
        ("juan carlos", "perez gomez"),
        ("Juan", "Pérez"),  # partial given names, only the paternal surname, accents
        ("Carlos Juan", "Gómez Pérez"),  # order is ignored
        ("  Juan   Carlos ", " PEREZ  "),
    ],
)
def test_matches_equivalent_declarations(first: str, last: str) -> None:
    assert names_match(ProvidedName(first, last), REGISTERED)


@pytest.mark.parametrize(
    ("first", "last"),
    [
        ("PEDRO", "PEREZ GOMEZ"),  # other given name
        ("JUAN", "GOMEZ"),  # paternal surname missing
        ("JUAN", "PEREZ LOPEZ"),  # surname the registry does not hold
        ("JUAN CARLOS ANDRES", "PEREZ"),  # extra given name
        ("", "PEREZ"),
        ("JUAN", ""),
        ("1234", "5678"),
    ],
)
def test_rejects_other_people(first: str, last: str) -> None:
    assert not names_match(ProvidedName(first, last), REGISTERED)


def test_handles_the_letter_enie() -> None:
    registered = RegisteredName("MARIA", "NUÑEZ", "QUISPE")
    assert names_match(ProvidedName("Maria", "Nuñez"), registered)
    assert names_match(ProvidedName("Maria", "NUNEZ"), registered)
