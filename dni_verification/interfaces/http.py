import json
import logging
from typing import Any

import azure.functions as func

from dni_verification.application.ports import RegistryUnavailableError
from dni_verification.application.services import VerifyDniService
from dni_verification.domain.dni import DniNumber, InvalidDniError
from dni_verification.domain.models import ProvidedName, VerificationResult

logger = logging.getLogger(__name__)


def _json(body: dict[str, Any], status_code: int) -> func.HttpResponse:
    return func.HttpResponse(json.dumps(body), status_code=status_code, mimetype="application/json")


def _problem(status_code: int, title: str, detail: str, reason: str | None = None) -> func.HttpResponse:
    body: dict[str, Any] = {"title": title, "detail": detail, "status": status_code}
    if reason:
        body["reason"] = reason
    return _json(body, status_code)


def _to_body(result: VerificationResult, investor_id: str | None) -> dict[str, Any]:
    registered = result.registered_name
    return {
        "investorId": investor_id,
        "dni": result.dni,
        "status": result.status.value,
        "registeredName": None
        if registered is None
        else {
            "firstNames": registered.first_names,
            "paternalSurname": registered.paternal_surname,
            "maternalSurname": registered.maternal_surname,
        },
        "source": result.source,
        "checkedAt": result.checked_at.isoformat(),
    }


def _text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""


def verify_dni(req: func.HttpRequest, service: VerifyDniService) -> func.HttpResponse:
    try:
        payload = req.get_json()
    except ValueError:
        return _problem(400, "Solicitud inválida", "El cuerpo debe ser JSON.")
    if not isinstance(payload, dict):
        return _problem(400, "Solicitud inválida", "El cuerpo debe ser un objeto JSON.")

    first_name, last_name = _text(payload, "firstName"), _text(payload, "lastName")
    if not first_name or not last_name:
        return _problem(400, "Solicitud inválida", "firstName y lastName son obligatorios.")

    try:
        dni = DniNumber(_text(payload, "dni"))
    except InvalidDniError as error:
        return _problem(400, "DNI inválido", str(error))

    investor_id = _text(payload, "investorId") or None
    try:
        result = service.verify(dni, ProvidedName(first_name, last_name))
    except RegistryUnavailableError as error:
        logger.error("DNI source unavailable (dni=%s): %s", dni.masked, error)
        return _problem(
            502,
            "Fuente no disponible",
            "No se pudo consultar el registro de DNI. Reintentar luego.",
            reason=str(error),
        )

    logger.info("DNI verified (dni=%s, status=%s)", dni.masked, result.status.value)
    return _json(_to_body(result, investor_id), 200)


def health() -> func.HttpResponse:
    return _json({"status": "UP"}, 200)
