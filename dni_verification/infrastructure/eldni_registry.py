import logging

import httpx
from bs4 import BeautifulSoup

from dni_verification.application.ports import RegistryUnavailableError
from dni_verification.domain.dni import DniNumber
from dni_verification.domain.models import RegisteredName

logger = logging.getLogger(__name__)

_SEARCH_PATH = "/pe/buscar-datos-por-dni"
_USER_AGENT = "Mozilla/5.0 (compatible; VankooDniVerification/0.1)"
_CSRF_EXPIRED = 419  # Laravel's answer to a stale or missing _token
_NOT_FOUND_MESSAGE = "No se encontraron datos"


class EldniRegistry:
    """Looks a DNI up on eldni.com by replaying the form a person would fill in.

    The site is a Laravel app: the page carries a CSRF `_token` that must be sent back
    together with the session cookie. The answer is a table with one row
    `DNI | Nombres | Apellido Paterno | Apellido Materno`; for an unknown DNI the row is empty
    and the page says "No se encontraron datos" (checked against the live site, Nov 2026).
    It is public data but not the official RENIEC service, so the HTML may change.
    """

    source = "eldni.com"

    def __init__(self, client: httpx.Client, base_url: str = "https://eldni.com", retries: int = 1) -> None:
        self._client = client
        self._base_url = base_url
        self._retries = retries

    def lookup(self, dni: DniNumber) -> RegisteredName | None:
        last_error: Exception | None = None
        for attempt in range(self._retries + 1):
            try:
                return self._lookup_once(dni)
            except (httpx.HTTPError, RegistryUnavailableError) as error:
                last_error = error
                logger.warning("eldni.com lookup failed (dni=%s, attempt=%d): %s", dni.masked, attempt + 1, error)
        raise RegistryUnavailableError("No se pudo consultar eldni.com.") from last_error

    def _lookup_once(self, dni: DniNumber) -> RegisteredName | None:
        # A new cookie jar per lookup: the session only has to live for this one form.
        self._client.cookies.clear()
        token = self._fetch_token()
        response = self._client.post(
            self._base_url + _SEARCH_PATH,
            data={"_token": token, "dni": dni.value},
            files={"_": (None, "")},  # forces multipart/form-data, as the real form sends
            headers={"User-Agent": _USER_AGENT, "Referer": self._base_url + "/"},
        )
        if response.status_code == _CSRF_EXPIRED:
            raise RegistryUnavailableError("eldni.com rechazó el token CSRF.")
        response.raise_for_status()
        return self._parse_result(response.text, dni)

    def _fetch_token(self) -> str:
        response = self._client.get(self._base_url + "/", headers={"User-Agent": _USER_AGENT})
        response.raise_for_status()
        field = BeautifulSoup(response.text, "html.parser").select_one(
            "form#buscar-datos-por-dni input[name=_token]"
        )
        token = field.get("value") if field else None
        if not isinstance(token, str) or not token:
            raise RegistryUnavailableError("No se encontró el token CSRF en eldni.com.")
        return token

    @staticmethod
    def _parse_result(html: str, dni: DniNumber) -> RegisteredName | None:
        soup = BeautifulSoup(html, "html.parser")
        row = soup.select_one("table tbody tr")
        cells = [cell.get_text(strip=True) for cell in row.find_all("td")] if row else []
        if len(cells) != 4:
            raise RegistryUnavailableError("La respuesta de eldni.com no tiene el formato esperado.")

        found_dni, first_names, paternal, maternal = cells
        if not any(cells):
            # An empty table alone proves nothing: the home page has one too, and it is what
            # comes back when the form is silently rejected. Only the site's explicit message
            # means "this DNI does not exist" (which makes profile reject the investor).
            notice = soup.select_one(".text-error")
            if notice is not None and _NOT_FOUND_MESSAGE in notice.get_text():
                return None
            raise RegistryUnavailableError("La respuesta de eldni.com está vacía sin indicar que el DNI no existe.")
        if found_dni != dni.value or not first_names or not paternal:
            raise RegistryUnavailableError("La respuesta de eldni.com no corresponde al DNI consultado.")
        return RegisteredName(first_names, paternal, maternal)
