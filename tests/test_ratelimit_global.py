"""
RATE_LIMIT has to actually limit.

Building slowapi's Limiter is not enough: `default_limits` are applied by its
middleware, and Buraq only built the limiter. So RATE_LIMIT -- documented as
applying to every route, and named in the admin documentation as what protects
the login page -- did nothing, and every route was unlimited.

    RATE_LIMIT = "3/minute", 6 requests to an undecorated route:
      [200, 200, 200, 200, 200, 200]
"""

import importlib.util
import warnings

import pytest
from fastapi.testclient import TestClient
from starlette.responses import PlainTextResponse

from buraq.conf import settings
from buraq.decorators import ratelimit
from buraq.urls import path

#: `limits` is optional -- only a counter shared between workers needs it. The
#: tests covering that path skip without it rather than failing, since a
#: contributor who has not installed an optional extra has not broken anything.
needs_limits = pytest.mark.skipif(
    importlib.util.find_spec("limits") is None,
    reason="limits is optional; install buraq[ratelimit-shared] to run this",
)


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
    assert "GlobalRateLimitMiddleware" not in names
    assert "SlowAPIMiddleware" not in names


def test_the_global_limit_does_not_use_slowapis_middleware(monkeypatch):
    """
    SlowAPIMiddleware finds the handler with _find_route_handler, which matches
    the request against every route on every request and never breaks early. So
    its cost grew with the project: measured on this application, enforcement
    cost 207us at five routes and 415us at two hundred, for a check worth 20us.

    A global limit applies to everything, so there is no handler to look up.
    """
    monkeypatch.setattr(settings, "RATE_LIMIT", "5/minute", raising=False)
    from buraq.core.application import Buraq

    names = [m.cls.__name__ for m in Buraq().user_middleware]
    assert "GlobalRateLimitMiddleware" in names
    assert "SlowAPIMiddleware" not in names, "the per-request route scan is back"


def test_the_limit_is_per_client_not_global(monkeypatch):
    """One client exhausting the limit must not lock everyone else out."""
    client = _client(monkeypatch, "2/minute")
    for _ in range(3):
        client.get("/x", headers={"X-Forwarded-For": "10.0.0.1"})

    assert client.get("/x", headers={"X-Forwarded-For": "10.0.0.1"}).status_code == 429
    assert client.get("/x", headers={"X-Forwarded-For": "10.0.0.2"}).status_code == 200


def test_a_rejection_says_how_long_to_wait(monkeypatch):
    """Without Retry-After a client retries straight back into the same wall."""
    client = _client(monkeypatch, "1/minute")
    client.get("/x")
    response = client.get("/x")

    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"


def test_a_proxied_client_is_read_from_the_forwarded_header(monkeypatch):
    """Behind a proxy every request has the proxy's address, so limiting on the
    socket would count the whole site as one client and lock it out at once."""
    client = _client(monkeypatch, "2/minute")
    codes = [
        client.get("/x", headers={"X-Forwarded-For": f"10.0.0.{i}"}).status_code
        for i in range(6)
    ]
    assert codes == [200] * 6, "distinct forwarded clients share the proxy's address"


def test_a_blocking_storage_uri_is_refused():
    """
    The synchronous clients in `limits` do blocking socket I/O. One of those on
    the request path stalls every request the worker is serving, not just the
    one being checked -- the whole point of an async framework is that it does
    not do this. The async client is a URI prefix away, so say so.
    """
    from buraq.exceptions import ImproperlyConfigured
    from buraq.middleware.ratelimit import GlobalRateLimitMiddleware

    with pytest.raises(ImproperlyConfigured, match="block the event loop"):
        GlobalRateLimitMiddleware(None, "5/minute", "redis://localhost:6379")


def test_the_refusal_names_the_fix():
    from buraq.exceptions import ImproperlyConfigured
    from buraq.middleware.ratelimit import GlobalRateLimitMiddleware

    with pytest.raises(ImproperlyConfigured) as caught:
        GlobalRateLimitMiddleware(None, "5/minute", "redis://localhost:6379")
    assert "async+redis://localhost:6379" in str(caught.value)


@needs_limits
def test_an_async_storage_uri_is_accepted():
    """`async+memory://` needs no server, so the async path is testable here."""
    from buraq.middleware.ratelimit import GlobalRateLimitMiddleware

    assert GlobalRateLimitMiddleware(None, "5/minute", "async+memory://") is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "storage",
    ["memory://", pytest.param("async+memory://", marks=needs_limits)],
)
async def test_every_backend_actually_limits(storage):
    """Buraq's own in-process counter, and the `limits`-backed shared one."""
    from buraq.middleware.ratelimit import RateLimiter
    from buraq.ratelimit import parse_rate

    limiter = RateLimiter(storage)
    rate = parse_rate("2/minute")
    results = [bool(await limiter.check(rate, "1.2.3.4")) for _ in range(3)]
    assert results == [True, True, False]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "storage",
    ["memory://", pytest.param("async+memory://", marks=needs_limits)],
)
async def test_every_backend_reports_what_is_left(storage):
    """The headers a client paces itself by are only as good as these numbers."""
    from buraq.middleware.ratelimit import RateLimiter
    from buraq.ratelimit import parse_rate

    limiter = RateLimiter(storage)
    rate = parse_rate("3/minute")
    assert [(await limiter.check(rate, "k")).remaining for _ in range(4)] == [2, 1, 0, 0]


@pytest.mark.asyncio
async def test_one_limiter_counts_several_limits_separately():
    """@ratelimit routes share a limiter, so its limits must not share a counter."""
    from buraq.middleware.ratelimit import RateLimiter
    from buraq.ratelimit import parse_rate

    limiter = RateLimiter("memory://")
    tight, loose = parse_rate("1/minute"), parse_rate("100/minute")

    assert bool(await limiter.check(tight, "1.2.3.4")) is True
    assert bool(await limiter.check(tight, "1.2.3.4")) is False
    assert bool(await limiter.check(loose, "1.2.3.4")) is True, "separate count"


def test_the_default_storage_setting_is_empty():
    """Empty means "follow the cache" -- see resolve_storage below."""
    from buraq.conf.defaults import BuraqSettings

    assert BuraqSettings.model_fields["RATE_LIMIT_STORAGE"].default == ""


def test_a_project_with_no_cache_configured_needs_nothing_running(monkeypatch):
    """The default has to stay zero-setup for a project that has not asked for
    a shared counter."""
    from buraq.middleware.ratelimit import resolve_storage

    monkeypatch.setattr(settings, "CACHE_REDIS_URL", None, raising=False)
    monkeypatch.setattr(settings, "RATE_LIMIT_STORAGE", "", raising=False)
    assert resolve_storage() == "memory://"


@pytest.mark.parametrize(
    "uri,package",
    [
        ("async+redis://localhost:6379", "coredis"),
        ("async+mongodb://localhost:27017", "motor"),
    ],
)
@needs_limits
def test_a_missing_driver_names_the_package_to_install(uri, package):
    """
    None of these clients is a dependency -- a project on the default in-process
    counter should not carry a Redis client. `limits` reports a missing one by
    naming the module it tried to import ("motor.motor_asyncio"), which is not
    what you type at a prompt.

    Skipped once the driver is installed, since then there is nothing to report.
    """
    from buraq.exceptions import ImproperlyConfigured
    from buraq.middleware.ratelimit import GlobalRateLimitMiddleware

    try:
        GlobalRateLimitMiddleware(None, "5/minute", uri)
    except ImproperlyConfigured as exc:
        assert f"pip install {package}" in str(exc)
    except Exception:
        pytest.skip(f"{package} is installed; nothing to report")


@pytest.mark.parametrize(
    "key,expected",
    [
        # By address, one user on three addresses is three clients.
        ("ip", [200, 200, 200]),
        # By identity, they are one -- and the third call is over the limit.
        ("user", [200, 200, 429]),
    ],
)
def test_key_decides_what_counts_as_one_client(monkeypatch, key, expected):
    """
    An office behind one address is a single IP, so limiting a signed-in action
    by address rations it across everyone there — and lets one user reset their
    own allowance by changing networks. `key="user"` counts the user instead.
    """
    monkeypatch.setattr(settings, "RATE_LIMIT", "", raising=False)
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    monkeypatch.setattr(settings, "MIDDLEWARE", [], raising=False)
    from buraq.core.application import Buraq

    class _User:
        is_authenticated = True

        def __init__(self, pk):
            self.pk = pk

    class _Auth:
        """Stands in for the auth middleware, which needs a real session."""

        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                pk = dict(scope["headers"]).get(b"x-user")
                scope["user"] = _User(int(pk)) if pk else None
            await self.app(scope, receive, send)

    @ratelimit("2/minute", key=key)
    async def profile(request):
        return PlainTextResponse("ok")

    app = Buraq()
    app.load_urls([path("/me", profile, name="me")])
    app.add_middleware(_Auth)
    client = TestClient(app)

    codes = [
        client.get(
            "/me", headers={"x-user": "7", "x-forwarded-for": f"10.0.0.{i}"}
        ).status_code
        for i in range(1, 4)
    ]
    assert codes == expected


def test_two_users_behind_one_address_do_not_share_an_allowance(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT", "", raising=False)
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    monkeypatch.setattr(settings, "MIDDLEWARE", [], raising=False)
    from buraq.core.application import Buraq

    class _User:
        is_authenticated = True

        def __init__(self, pk):
            self.pk = pk

    class _Auth:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                pk = dict(scope["headers"]).get(b"x-user")
                scope["user"] = _User(int(pk)) if pk else None
            await self.app(scope, receive, send)

    @ratelimit("1/minute", key="user")
    async def profile(request):
        return PlainTextResponse("ok")

    app = Buraq()
    app.load_urls([path("/me", profile, name="me")])
    app.add_middleware(_Auth)
    client = TestClient(app)

    def call(pk):
        return client.get(
            "/me", headers={"x-user": pk, "x-forwarded-for": "10.0.0.1"}
        ).status_code

    assert call("7") == 200
    assert call("7") == 429, "the same user, spent"
    assert call("8") == 200, "a different user on the same address"


def test_two_routes_with_the_same_limit_do_not_share_a_counter(monkeypatch):
    """
    `limits` derives its storage key from the limit and the identifier, so two
    views both carrying "5/minute" landed in one bucket for a given caller:
    spending the login allowance spent the signup one too, and the second view
    answered 429 on its very first request.

        /login  [200, 200, 429]
        /signup [429, 429, 429]   <- never called before
    """
    monkeypatch.setattr(settings, "RATE_LIMIT", "", raising=False)
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    from buraq.core.application import Buraq

    @ratelimit("2/minute")
    async def login(request):
        return PlainTextResponse("ok")

    @ratelimit("2/minute")
    async def signup(request):
        return PlainTextResponse("ok")

    app = Buraq()
    app.load_urls(
        [path("/login", login, name="i"), path("/signup", signup, name="u")]
    )
    client = TestClient(app)

    assert [client.get("/login").status_code for _ in range(3)] == [200, 200, 429]
    assert [client.get("/signup").status_code for _ in range(3)] == [200, 200, 429]


def test_a_route_limit_is_separate_from_the_global_one(monkeypatch):
    """The global limit counts every route together; a route's counts only it."""
    monkeypatch.setattr(settings, "RATE_LIMIT", "100/minute", raising=False)
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    from buraq.core.application import Buraq

    @ratelimit("2/minute")
    async def tight(request):
        return PlainTextResponse("ok")

    async def plain(request):
        return PlainTextResponse("ok")

    app = Buraq()
    app.load_urls([path("/t", tight, name="t"), path("/x", plain, name="x")])
    client = TestClient(app)

    assert [client.get("/t").status_code for _ in range(3)] == [200, 200, 429]
    assert client.get("/x").status_code == 200, "the global limit is nowhere near spent"


# --- what the client is told -------------------------------------------------


def test_a_response_says_how_much_allowance_is_left(monkeypatch):
    """
    A client that cannot see what it has left has to discover the limit by
    hitting it. These are the headers GitHub, Stripe and every other public API
    send; neither slowapi nor DRF sends them.
    """
    client = _client(monkeypatch, "5/minute")
    response = client.get("/x")

    assert response.headers["x-ratelimit-limit"] == "5"
    assert response.headers["x-ratelimit-remaining"] == "4"
    assert int(response.headers["x-ratelimit-reset"]) > 0


def test_the_allowance_counts_down_across_requests(monkeypatch):
    client = _client(monkeypatch, "5/minute")
    left = [client.get("/x").headers["x-ratelimit-remaining"] for _ in range(3)]
    assert left == ["4", "3", "2"]


def test_a_rejection_carries_the_headers_too(monkeypatch):
    client = _client(monkeypatch, "1/minute")
    client.get("/x")
    response = client.get("/x")

    assert response.status_code == 429
    assert response.headers["x-ratelimit-remaining"] == "0"
    assert response.headers["retry-after"] == response.headers["x-ratelimit-reset"]


# --- cost and exempt ---------------------------------------------------------


def test_cost_weights_an_expensive_route(monkeypatch):
    """A report that costs a second of database time should not be one call."""
    monkeypatch.setattr(settings, "RATE_LIMIT", "", raising=False)
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    from buraq.core.application import Buraq

    @ratelimit("10/minute", cost=5)
    async def report(request):
        return PlainTextResponse("ok")

    app = Buraq()
    app.load_urls([path("/r", report, name="r")])
    client = TestClient(app)

    assert [client.get("/r").status_code for _ in range(3)] == [200, 200, 429]


def test_exempt_skips_the_limit(monkeypatch):
    """For a health check, or a staff user who should not be throttled."""
    monkeypatch.setattr(settings, "RATE_LIMIT", "", raising=False)
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    from buraq.core.application import Buraq

    @ratelimit("1/minute", exempt=lambda r: r.headers.get("x-internal") == "yes")
    async def guarded(request):
        return PlainTextResponse("ok")

    app = Buraq()
    app.load_urls([path("/g", guarded, name="g")])
    client = TestClient(app)

    exempt = [
        client.get("/g", headers={"x-internal": "yes"}).status_code for _ in range(4)
    ]
    assert exempt == [200] * 4
    assert [client.get("/g").status_code for _ in range(2)] == [200, 429]


@pytest.mark.parametrize("bad", [0, -1, 1.5, "5", True])
def test_a_cost_that_is_not_a_positive_whole_number_is_refused(bad):
    with pytest.raises(ValueError, match="whole number"):
        ratelimit("5/minute", cost=bad)


def test_an_exempt_that_is_not_callable_is_refused():
    with pytest.raises(ValueError, match="function of the request"):
        ratelimit("5/minute", exempt="staff")


def test_the_default_path_does_not_need_the_limits_package(monkeypatch):
    """
    `limits` is an optional install now, for a counter shared between workers.
    A project on the in-process default should not carry it, so nothing on that
    path may import it.
    """
    import sys

    monkeypatch.setattr(settings, "RATE_LIMIT", "2/minute", raising=False)
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)

    class _Block:
        def find_spec(self, name, path=None, target=None):
            if name.split(".")[0] == "limits":
                raise ImportError("limits is blocked for this test")
            return None

    blocker = _Block()
    sys.meta_path.insert(0, blocker)
    try:
        from buraq.core.application import Buraq

        async def plain(request):
            return PlainTextResponse("ok")

        app = Buraq()
        app.load_urls([path("/x", plain, name="x")])
        client = TestClient(app)
        assert [client.get("/x").status_code for _ in range(3)] == [200, 200, 429]
    finally:
        sys.meta_path.remove(blocker)


def test_a_limited_route_reports_its_own_allowance_not_the_global_one(monkeypatch):
    """
    A login route capped at 5/minute under a global 100/minute reported
    `X-RateLimit-Limit: 100, Remaining: 99`. A client pacing itself by that
    would think it had 99 calls left when it had 4 -- worse than no headers.
    """
    monkeypatch.setattr(settings, "RATE_LIMIT", "100/minute", raising=False)
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    from buraq.core.application import Buraq

    @ratelimit("5/minute")
    async def login(request):
        return PlainTextResponse("ok")

    async def plain(request):
        return PlainTextResponse("ok")

    app = Buraq()
    app.load_urls([path("/login", login, name="l"), path("/p", plain, name="p")])
    client = TestClient(app)

    limited = client.get("/login").headers
    assert limited["x-ratelimit-limit"] == "5"
    assert limited["x-ratelimit-remaining"] == "4"

    assert client.get("/p").headers["x-ratelimit-limit"] == "100", "global elsewhere"


def test_the_headers_are_not_sent_twice(monkeypatch):
    """
    The global middleware appended its own on top of the route's, so a client
    read `X-RateLimit-Limit: 5, 100` -- one header, two values, joined by the
    comma that makes it unparseable.
    """
    monkeypatch.setattr(settings, "RATE_LIMIT", "100/minute", raising=False)
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    from buraq.core.application import Buraq

    @ratelimit("5/minute")
    async def login(request):
        return PlainTextResponse("ok")

    app = Buraq()
    app.load_urls([path("/login", login, name="l")])

    response = TestClient(app).get("/login")
    for header in ("x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset"):
        assert "," not in response.headers[header], f"{header} sent twice"


def test_a_route_with_two_limits_reports_the_tighter_one(monkeypatch):
    """'50/day' with 2 left matters more to a caller than '5/minute' with 4."""
    monkeypatch.setattr(settings, "RATE_LIMIT", "", raising=False)
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    from buraq.core.application import Buraq

    @ratelimit("50/day", "5/minute")
    async def send(request):
        return PlainTextResponse("ok")

    app = Buraq()
    app.load_urls([path("/s", send, name="s")])
    client = TestClient(app)

    left = [client.get("/s").headers["x-ratelimit-remaining"] for _ in range(3)]
    assert left == ["4", "3", "2"], "one call spends one from each, and 5/minute binds"


def test_the_headers_appear_with_the_global_limit_off(monkeypatch):
    """@ratelimit is what limits here, so it is what has to report."""
    monkeypatch.setattr(settings, "RATE_LIMIT", "", raising=False)
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    from buraq.core.application import Buraq

    @ratelimit("5/minute")
    async def login(request):
        return PlainTextResponse("ok")

    app = Buraq()
    app.load_urls([path("/login", login, name="l")])

    assert TestClient(app).get("/login").headers["x-ratelimit-limit"] == "5"


def test_the_global_limit_and_the_routes_share_one_store(monkeypatch):
    """
    The middleware built a second RateLimiter of its own, so a project ran two
    in-process backends -- two LRUs, twice the memory bound -- and a shared
    RATE_LIMIT_STORAGE opened two connections to count into one place.
    """
    monkeypatch.setattr(settings, "RATE_LIMIT", "100/minute", raising=False)
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    from buraq.core.application import Buraq

    app = Buraq()
    middleware = next(
        m for m in app.user_middleware if m.cls.__name__ == "GlobalRateLimitMiddleware"
    )
    assert middleware.kwargs.get("limiter") is app.state.limiter


# --- where the counters go ---------------------------------------------------


def _resolve(monkeypatch, cache=None, setting="", limits_installed=True):
    """Resolve storage with `limits` reported as installed unless asked otherwise.

    What these check is the resolution -- which setting wins, and how a cache URL
    is turned into a store -- not whether an optional package happens to be
    present. Left to the real check they passed or failed by what the machine had
    installed, which is how they passed here and failed in CI.
    """
    from buraq.middleware import ratelimit as module

    monkeypatch.setattr(module, "_limits_installed", lambda: limits_installed)
    monkeypatch.setattr(settings, "CACHE_REDIS_URL", cache, raising=False)
    monkeypatch.setattr(settings, "RATE_LIMIT_STORAGE", setting, raising=False)
    return module.resolve_storage()


def test_the_counters_follow_the_cache_when_it_is_redis(monkeypatch):
    """
    A project running Redis for its cache has already said where its shared
    state lives. Making it name the same server again, in a second setting and
    a second format, is two places to change one address and one to forget.
    """
    assert _resolve(monkeypatch, cache="redis://localhost:6379") == (
        "async+redis://localhost:6379"
    )


def test_a_project_with_no_redis_cache_counts_in_its_own_process(monkeypatch):
    assert _resolve(monkeypatch, cache=None) == "memory://"


def test_an_explicit_setting_wins_over_the_cache(monkeypatch):
    """Including "memory://", to keep the count per-worker on purpose."""
    assert _resolve(monkeypatch, cache="redis://localhost:6379", setting="memory://") == (
        "memory://"
    )
    assert _resolve(
        monkeypatch, cache="redis://localhost:6379", setting="async+redis://other:6379"
    ) == "async+redis://other:6379"


def test_a_cache_url_that_is_already_async_is_not_prefixed_twice(monkeypatch):
    assert _resolve(monkeypatch, cache="async+redis://c:6379") == "async+redis://c:6379"


def test_following_the_cache_without_limits_warns_rather_than_failing(monkeypatch):
    """
    Refusing to start would turn "added a Redis cache" into a startup failure.
    Counting per worker is what the project had before it followed the cache at
    all, so the limit still works -- but silently counting N times the limit
    across N workers is not something to discover in production.
    """
    from buraq.middleware import ratelimit as module

    monkeypatch.setattr(module, "_limits_installed", lambda: False)
    monkeypatch.setattr(settings, "CACHE_REDIS_URL", "redis://c:6379", raising=False)
    monkeypatch.setattr(settings, "RATE_LIMIT_STORAGE", "", raising=False)

    with pytest.warns(RuntimeWarning, match="counted per worker"):
        assert module.resolve_storage() == "memory://"


def test_no_warning_when_the_per_worker_count_was_asked_for(monkeypatch):
    """An explicit "memory://" is a decision, not an accident."""
    from buraq.middleware import ratelimit as module

    monkeypatch.setattr(module, "_limits_installed", lambda: False)
    monkeypatch.setattr(settings, "CACHE_REDIS_URL", "redis://c:6379", raising=False)
    monkeypatch.setattr(settings, "RATE_LIMIT_STORAGE", "memory://", raising=False)

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert module.resolve_storage() == "memory://"
