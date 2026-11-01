import pytest

from dni_verification.domain.dni import DniNumber, InvalidDniError


def test_accepts_eight_digits() -> None:
    assert DniNumber("12345678").value == "12345678"


@pytest.mark.parametrize("raw", ["", "1234567", "123456789", "1234567a", " 12345678", "١٢٣٤٥٦٧٨"])
def test_rejects_anything_but_eight_ascii_digits(raw: str) -> None:
    with pytest.raises(InvalidDniError):
        DniNumber(raw)


def test_masked_hides_the_last_four_digits() -> None:
    assert DniNumber("12345678").masked == "1234****"
