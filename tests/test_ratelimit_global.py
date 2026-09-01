"""
RATE_LIMIT has to actually limit.

Building slowapi's Limiter is not enough: `default_limits` are applied by its
middleware, and Buraq only built the limiter. So RATE_LIMIT -- documented as
applying to every route, and named in the admin documentation as what protects
the login page -- did nothing, and every route was unlimited.

    RATE_LIMIT = "3/minute", 6 requests to an undecorated route:
      [200, 200, 200, 200, 200, 200]
"""

import pytest
from fastapi.testclient import TestClient
from starlette.responses import PlainTextResponse

from buraq.conf import settings
from buraq.decorators import ratelimit
from buraq.urls import path


def _client(monkeypatch, limit, views=None):
    monkeypatch.setattr(settings, "RATE_LIMIT", limit, raising=False)
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    from buraq.core.application import Buraq

    async def plain(request):
        return PlainTextResponse("ok")

    app = Buraq()
    app.load_urls(views(plain) if views else [path("/x", plain, name="x")])
    return TestClient(app)


def test_the_global_limit_is_enforced(monkeypatch):
    client = _client(monkeypatch, "3/minute")
    codes = [client.get("/x").status_code for _ in range(6)]

    assert codes[:3] == [200, 200, 200]
    assert 429 in codes, "an undecorated route must still obey RATE_LIMIT"


def test_over_the_limit_is_429(monkeypatch):
    client = _client(monkeypatch, "1/minute")
    client.get("/x")
    assert client.get("/x").status_code == 429


def test_an_empty_limit_turns_it_off(monkeypatch):
    """For an application behind something that already limits by IP."""
    client = _client(monkeypatch, "")
    assert [client.get("/x").status_code for _ in range(10)] == [200] * 10


def test_a_per_route_limit_still_works_with_the_global_one_off(monkeypatch):
    """Turning off the global limit must not disable @ratelimit."""

    def views(plain):
        @ratelimit("2/minute")
        async def tight(request):
            return PlainTextResponse("ok")

        return [path("/x", plain, name="x"), path("/t", tight, name="t")]

    client = _client(monkeypatch, "", views=views)
    assert [client.get("/x").status_code for _ in range(5)] == [200] * 5
    codes = [client.get("/t").status_code for _ in range(4)]
    assert codes[:2] == [200, 200]
    assert 429 in codes


def test_a_per_route_limit_can_be_tighter_than_the_global_one(monkeypatch):
    def views(plain):
        @ratelimit("2/minute")
        async def tight(request):
            return PlainTextResponse("ok")

        return [path("/x", plain, name="x"), path("/t", tight, name="t")]

    client = _client(monkeypatch, "100/minute", views=views)
    codes = [client.get("/t").status_code for _ in range(4)]
    assert 429 in codes, "the route limit should bite before the global one"


@pytest.mark.parametrize("limit", ["", None])
def test_no_middleware_when_there_is_no_global_limit(monkeypatch, limit):
    """Enforcing costs a middleware pass per request; do not pay it for nothing."""
    monkeypatch.setattr(settings, "RATE_LIMIT", limit, raising=False)
    from buraq.core.application import Buraq

    app = Buraq()
    names = [m.cls.__name__ for m in app.user_middleware]
    assert "SlowAPIMiddleware" not in names
