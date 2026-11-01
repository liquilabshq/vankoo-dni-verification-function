from pathlib import Path

import httpx
import pytest

from dni_verification.application.ports import RegistryUnavailableError
from dni_verification.domain.dni import DniNumber
from dni_verification.domain.models import RegisteredName
from dni_verification.infrastructure.eldni_registry import EldniRegistry

FIXTURES = Path(__file__).parents[2] / "fixtures"
HOME = (FIXTURES / "eldni_home.html").read_text(encoding="utf-8")
FOUND = (FIXTURES / "eldni_result_found.html").read_text(encoding="utf-8")
NOT_FOUND = (FIXTURES / "eldni_result_not_found.html").read_text(encoding="utf-8")

DNI = DniNumber("12345678")


class FakeEldni:
    """Plays the two requests eldni.com expects and records what the scraper sent."""

    def __init__(self, post_status: int = 200, post_body: str = FOUND, home_body: str = HOME) -> None:
        self.post_status = post_status
        self.post_body = post_body
        self.home_body = home_body
        self.posts: list[httpx.Request] = []
        self.gets = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            self.gets += 1
            return httpx.Response(200, text=self.home_body, headers={"Set-Cookie": "laravel_session=abc; Path=/"})
        self.posts.append(request)
        return httpx.Response(self.post_status, text=self.post_body)


def make_registry(site: FakeEldni, retries: int = 0) -> EldniRegistry:
    client = httpx.Client(transport=httpx.MockTransport(site))
    return EldniRegistry(client, "https://eldni.com", retries)


def test_returns_the_registered_name() -> None:
    assert make_registry(FakeEldni()).lookup(DNI) == RegisteredName("JUAN CARLOS", "PEREZ", "GOMEZ")


def test_replays_the_form_with_the_csrf_token_and_the_session_cookie() -> None:
    site = FakeEldni()
    make_registry(site).lookup(DNI)

    post = site.posts[0]
    body = post.read().decode()
    assert str(post.url) == "https://eldni.com/pe/buscar-datos-por-dni"
    assert post.headers["content-type"].startswith("multipart/form-data")
    assert 'name="_token"' in body
    assert "TOKEN-DE-PRUEBA" in body
    assert 'name="dni"' in body
    assert "12345678" in body
    assert "laravel_session=abc" in post.headers["cookie"]


def test_returns_none_when_the_site_says_the_dni_does_not_exist() -> None:
    assert make_registry(FakeEldni(post_body=NOT_FOUND)).lookup(DNI) is None


@pytest.mark.parametrize(
    "site",
    [
        FakeEldni(post_status=500),
        FakeEldni(post_status=419),  # CSRF rejected
        FakeEldni(post_body="<html><body>Mantenimiento</body></html>"),  # no table
        FakeEldni(post_body=HOME),  # form silently rejected: empty table, no "not found" notice
        FakeEldni(home_body="<html><body>sin formulario</body></html>"),  # no token
        FakeEldni(post_body=FOUND.replace("12345678", "99999999")),  # answer for another DNI
    ],
    ids=["http-500", "csrf-419", "no-table", "empty-without-notice", "no-token", "other-dni"],
)
def test_unexpected_answers_are_reported_as_unavailable(site: FakeEldni) -> None:
    with pytest.raises(RegistryUnavailableError):
        make_registry(site).lookup(DNI)


def test_retries_before_giving_up() -> None:
    site = FakeEldni(post_status=500)
    with pytest.raises(RegistryUnavailableError):
        make_registry(site, retries=1).lookup(DNI)
    assert len(site.posts) == 2
    assert site.gets == 2  # each attempt starts a fresh session


def test_network_errors_are_reported_as_unavailable() -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout", request=request)

    registry = EldniRegistry(httpx.Client(transport=httpx.MockTransport(broken)), retries=0)
    with pytest.raises(RegistryUnavailableError):
        registry.lookup(DNI)


@pytest.mark.live
def test_live_unknown_shape_is_still_parseable() -> None:
    """Smoke test against the real site; run on demand with `pytest -m live`.

    Looks up DNI 00000000 (not a valid number) just to confirm the page structure still parses.
    """
    registry = EldniRegistry(httpx.Client(timeout=15, follow_redirects=True))
    assert registry.lookup(DniNumber("00000000")) is None
