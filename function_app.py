"""Azure Functions entry point (v2 programming model): only wiring, no logic."""

import azure.functions as func

from dni_verification.interfaces import http
from dni_verification.interfaces.composition import build_service

app = func.FunctionApp()
_service = build_service()


@app.function_name(name="verify_dni")
@app.route(route="verify-dni", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def verify_dni(req: func.HttpRequest) -> func.HttpResponse:
    return http.verify_dni(req, _service)


@app.function_name(name="health")
@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    return http.health()
