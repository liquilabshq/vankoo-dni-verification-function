import logging
from typing import Any

import httpx

from dni_verification.application.ports import RegistryUnavailableError
from dni_verification.domain.dni import DniNumber
from dni_verification.domain.models import RegisteredName

logger = logging.getLogger(__name__)

# Mensaje con el que la API contesta cuando el DNI no existe (spec OpenAPI de API Perú, POST /dni).
_NOT_FOUND_MESSAGE = "No se encontró DNI"


class ApiPeruRegistry:
    """Consulta un DNI en la API REST de API Perú (https://apiperu.pe).

    `POST {base_url}/dni` con `{"dni": "<8 dígitos>"}` y `Authorization: Bearer <token>`.
    Solo se envía el DNI (nunca los nombres declarados) y de la respuesta solo se usan los tres
    campos de nombre: la dirección y el ubigeo se ignoran a propósito.

    Qué es un veredicto y qué no, como en el scraper: solo un 200 coherente o el 404 con el mensaje
    exacto de «no existe» valen. Un 401 (token inválido o ausente), 429 (cuota), un 5xx o un formato
    inesperado son fallos de la fuente, nunca un `NOT_FOUND`, que provocaría el rechazo de un inversor.
    """

    source = "apiperu.pe"

    def __init__(
        self,
        client: httpx.Client,
        token: str,
        base_url: str = "https://api.apiperu.pe",
        retries: int = 1,
    ) -> None:
        if not token:
            raise ValueError("El token de API Perú es obligatorio.")
        self._client = client
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._retries = retries

    def lookup(self, dni: DniNumber) -> RegisteredName | None:
        response = self._post_with_retries(dni)
        return self._interpret(response, dni)

    def _post_with_retries(self, dni: DniNumber) -> httpx.Response:
        last_error: httpx.TransportError | None = None
        for attempt in range(self._retries + 1):
            try:
                return self._client.post(
                    f"{self._base_url}/dni",
                    json={"dni": dni.value},
                    headers={"Authorization": f"Bearer {self._token}", "Accept": "application/json"},
                )
            except httpx.TransportError as error:
                # Solo los fallos de red se reintentan; los de la API (401, 429...) no mejoran reintentando.
                last_error = error
                logger.warning("apiperu.pe lookup failed (dni=%s, attempt=%d): %s", dni.masked, attempt + 1, error)
        raise RegistryUnavailableError(f"No se pudo consultar apiperu.pe: {last_error}") from last_error

    def _interpret(self, response: httpx.Response, dni: DniNumber) -> RegisteredName | None:
        if response.status_code == 404:
            if self._message(response) == _NOT_FOUND_MESSAGE:
                return None
            raise RegistryUnavailableError("apiperu.pe respondió 404 sin el aviso de DNI inexistente.")
        if response.status_code != 200:
            # Sin cuerpo en el mensaje: no hay motivo para arrastrar contenido de un tercero a nuestros logs.
            raise RegistryUnavailableError(f"apiperu.pe respondió HTTP {response.status_code}.")

        body = self._json(response)
        data = body.get("data")
        if body.get("success") is not True or not isinstance(data, dict):
            raise RegistryUnavailableError("La respuesta de apiperu.pe no tiene el formato esperado.")
        if data.get("numero") != dni.value:
            raise RegistryUnavailableError("La respuesta de apiperu.pe no corresponde al DNI consultado.")

        first_names = self._text(data, "nombres")
        paternal = self._text(data, "apellido_paterno")
        if not first_names or not paternal:
            raise RegistryUnavailableError("La respuesta de apiperu.pe no trae los nombres esperados.")
        return RegisteredName(first_names, paternal, self._text(data, "apellido_materno"))

    @staticmethod
    def _json(response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as error:
            raise RegistryUnavailableError("apiperu.pe no devolvió JSON.") from error
        if not isinstance(body, dict):
            raise RegistryUnavailableError("La respuesta de apiperu.pe no es un objeto JSON.")
        return body

    def _message(self, response: httpx.Response) -> str:
        try:
            message = self._json(response).get("message")
        except RegistryUnavailableError:
            return ""
        return message.strip() if isinstance(message, str) else ""

    @staticmethod
    def _text(data: dict[str, Any], key: str) -> str:
        value = data.get(key)
        return value.strip() if isinstance(value, str) else ""
