import json
from typing import Any

import azure.functions as func
import pytest

from dni_verification.application.services import VerifyDniService
from dni_verification.infrastructure.fake_registry import FakeDniRegistry
from dni_verification.interfaces import http


def make_request(body: Any) -> func.HttpRequest:
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    return func.HttpRequest(
        method="POST",
        url="/api/verify-dni",
        headers={"Content-Type": "application/json"},
        body=raw,
    )


def call(body: Any) -> tuple[int, dict[str, Any]]:
    response = http.verify_dni(make_request(body), VerifyDniService(FakeDniRegistry()))
    return response.status_code, json.loads(response.get_body())


VALID = {"investorId": "inv-1", "dni": "12345678", "firstName": "Juan Carlos", "lastName": "Perez Gomez"}


def test_verified() -> None:
    status, body = call(VALID)

    assert status == 200
    assert body["status"] == "VERIFIED"
    assert body["investorId"] == "inv-1"
    assert body["dni"] == "12345678"
    assert body["source"] == "fake"
    assert body["registeredName"] == {
        "firstNames": "JUAN CARLOS",
        "paternalSurname": "PEREZ",
        "maternalSurname": "GOMEZ",
    }
    assert "checkedAt" in body


def test_name_mismatch() -> None:
    status, body = call({**VALID, "firstName": "Pedro", "lastName": "Ramos"})

    assert status == 200
    assert body["status"] == "NAME_MISMATCH"


def test_not_found_has_no_registered_name() -> None:
    status, body = call({**VALID, "dni": "11111111"})

    assert status == 200
    assert body["status"] == "NOT_FOUND"
    assert body["registeredName"] is None


def test_investor_id_is_optional() -> None:
    status, body = call({k: v for k, v in VALID.items() if k != "investorId"})

    assert status == 200
    assert body["investorId"] is None


@pytest.mark.parametrize("dni", ["1234567", "abcdefgh", "", 12345678, None])
def test_invalid_dni_is_a_400(dni: Any) -> None:
    status, body = call({**VALID, "dni": dni})

    assert status == 400
    assert body["status"] == 400


@pytest.mark.parametrize("missing", ["firstName", "lastName"])
def test_names_are_required(missing: str) -> None:
    status, _ = call({k: v for k, v in VALID.items() if k != missing})

    assert status == 400


@pytest.mark.parametrize("body", [b"not json", b"[1, 2]", b'"text"'])
def test_non_object_json_is_a_400(body: bytes) -> None:
    status, _ = call(body)

    assert status == 400


def test_unavailable_source_is_a_502() -> None:
    status, body = call({**VALID, "dni": "00000503"})

    assert status == 502
    assert body["title"] == "Fuente no disponible"
    assert body["reason"] == "Fuente simulada no disponible."


def test_logs_never_contain_the_full_dni(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("INFO"):
        call(VALID)
        call({**VALID, "dni": "00000503"})

    assert "12345678" not in caplog.text
    assert "00000503" not in caplog.text
    assert "1234****" in caplog.text


def test_health() -> None:
    response = http.health()

    assert response.status_code == 200
    assert json.loads(response.get_body()) == {"status": "UP"}
