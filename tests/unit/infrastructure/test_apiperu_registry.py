import json
from typing import Any

import httpx
import pytest

from dni_verification.application.ports import RegistryUnavailableError
from dni_verification.domain.dni import DniNumber
from dni_verification.domain.models import RegisteredName
from dni_verification.infrastructure.apiperu_registry import ApiPeruRegistry

DNI = DniNumber("12345678")
TOKEN = "token-de-prueba-no-real"

# Mismo formato que el ejemplo del spec OpenAPI de API Perú, con datos inventados.
FOUND: dict[str, Any] = {
    "success": True,
    "message": "exito",
    "data": {
        "numero": "12345678",
        "codigo_verificacion": "9",
        "nombres": "JUAN CARLOS",
        "apellido_paterno": "PEREZ",
        "apellido_materno": "GOMEZ",
        "nombre_completo": "PEREZ GOMEZ, JUAN CARLOS",
        "direccion": "CALLE FALSA 123",
        "direccion_completa": "CALLE FALSA 123, LIMA - LIMA - LIMA",
        "ubigeo_reniec": "150101",
        "ubigeo_sunat": "150101",
    },
}
NOT_FOUND = {"success": False, "message": "No se encontró DNI"}


class FakeApi:
    """Hace de API Perú y guarda lo que le llegó, para comprobar qué sale de nuestra función."""

    def __init__(self, response: httpx.Response | Exception) -> None:
        self.response = response
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def make_registry(api: FakeApi, retries: int = 0) -> ApiPeruRegistry:
    client = httpx.Client(transport=httpx.MockTransport(api))
    return ApiPeruRegistry(client, TOKEN, "https://api.apiperu.pe", retries)


def test_returns_the_registered_name() -> None:
    registry = make_registry(FakeApi(httpx.Response(200, json=FOUND)))

    assert registry.lookup(DNI) == RegisteredName("JUAN CARLOS", "PEREZ", "GOMEZ")


def test_sends_only_the_dni_with_the_bearer_token() -> None:
    api = FakeApi(httpx.Response(200, json=FOUND))
    make_registry(api).lookup(DNI)

    request = api.requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.apiperu.pe/dni"
    assert request.headers["authorization"] == f"Bearer {TOKEN}"
    assert json.loads(request.content) == {"dni": "12345678"}  # ningún nombre sale hacia el tercero


def test_address_and_ubigeo_are_not_part_of_the_result() -> None:
    result = make_registry(FakeApi(httpx.Response(200, json=FOUND))).lookup(DNI)

    assert result is not None
    assert "CALLE" not in repr(result)


def test_an_empty_maternal_surname_is_accepted() -> None:
    body = {**FOUND, "data": {**FOUND["data"], "apellido_materno": ""}}

    result = make_registry(FakeApi(httpx.Response(200, json=body))).lookup(DNI)

    assert result == RegisteredName("JUAN CARLOS", "PEREZ", "")


def test_returns_none_only_with_the_not_found_notice() -> None:
    assert make_registry(FakeApi(httpx.Response(404, json=NOT_FOUND))).lookup(DNI) is None


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(404, json={"success": False, "message": "Bad Request"}),  # 404 sin el aviso de «no existe»
        httpx.Response(404, text="<html>no es json</html>"),
        httpx.Response(401),  # token inválido o ausente: observado en la API real
        httpx.Response(403, json={"message": "Forbidden"}),
        httpx.Response(429, json={"message": "cuota agotada"}),
        httpx.Response(500, text="error"),
        httpx.Response(200, text="no es json"),
        httpx.Response(200, json=[1, 2]),
        httpx.Response(200, json={"success": False, "message": "error"}),
        httpx.Response(200, json={"success": True, "message": "exito", "data": None}),
        httpx.Response(200, json={**FOUND, "data": {**FOUND["data"], "numero": "99999999"}}),  # DNI distinto del pedido
        httpx.Response(200, json={**FOUND, "data": {**FOUND["data"], "nombres": ""}}),
        httpx.Response(200, json={**FOUND, "data": {**FOUND["data"], "apellido_paterno": None}}),
    ],
    ids=[
        "404-other-message", "404-not-json", "401", "403", "429", "500", "200-not-json", "200-array",
        "200-success-false", "200-no-data", "200-other-dni", "200-no-first-names", "200-no-paternal",
    ],
)
def test_anything_unexpected_is_a_source_failure_never_not_found(response: httpx.Response) -> None:
    with pytest.raises(RegistryUnavailableError):
        make_registry(FakeApi(response)).lookup(DNI)


def test_network_errors_are_retried_and_then_reported() -> None:
    api = FakeApi(httpx.ConnectTimeout("timeout"))

    with pytest.raises(RegistryUnavailableError):
        make_registry(api, retries=1).lookup(DNI)

    assert len(api.requests) == 2


def test_http_errors_are_not_retried() -> None:
    api = FakeApi(httpx.Response(401))

    with pytest.raises(RegistryUnavailableError):
        make_registry(api, retries=3).lookup(DNI)

    assert len(api.requests) == 1  # reintentar un 401 o un 429 solo gastaría cuota


def test_errors_never_carry_the_token_or_the_dni() -> None:
    cases = [httpx.Response(401), httpx.Response(200, json={**FOUND, "data": {**FOUND["data"], "numero": "99999999"}})]
    for response in cases:
        with pytest.raises(RegistryUnavailableError) as excinfo:
            make_registry(FakeApi(response)).lookup(DNI)
        assert TOKEN not in str(excinfo.value)
        assert DNI.value not in str(excinfo.value)


def test_a_token_is_required() -> None:
    with pytest.raises(ValueError):
        ApiPeruRegistry(httpx.Client(), "")
