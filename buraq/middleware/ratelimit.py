"""
Rate limiting: the limiter, and the middleware that applies ``RATE_LIMIT``.

The counting itself lives in :mod:`buraq.ratelimit`, which Buraq owns. This
module picks a backend for it and puts it on the request path.

The in-process backend is ours: it is what nearly every project runs, it is
16x faster than the library we used before (1.0us against 16.6us), and owning
it means the common case carries no dependency at all.

A shared backend still goes through ``limits``, which becomes an optional
install. Doing check-and-increment atomically across processes is where rate
limiters go subtly wrong, and that correctness is worth more than the
dependency -- particularly since nothing here can test it without a live server.

This replaced slowapi, which was wrong for the job in three ways: its middleware
matched the request against every route on every request to find the handler
(207us of enforcement at five routes, 415us at two hundred, for a check worth
20us); its default strategy was a fixed window, which admits twice the limit
across a boundary; and it could not use an async store at all.
"""
from __future__ import annotations

import time

from buraq.exceptions import ImproperlyConfigured
from buraq.ratelimit import MemoryBackend, Rate, Verdict, parse_rate

__all__ = [
    "GlobalRateLimitMiddleware",
    "RateLimiter",
    "client_ip",
    "rate_headers",
    "resolve_storage",
]


def resolve_storage(storage: str | None = None) -> str:
    """Where the counters go, given RATE_LIMIT_STORAGE and the cache settings.

    An empty setting means "wherever the cache is". A project running Redis for
    its cache has already said where its shared state lives, and making it name
    the same server again -- in a second setting, in a second format -- is two
    places to change one address, and one of them to forget.

    A Redis cache therefore gives correct limits across workers by default,
    rather than four workers quietly admitting four times the limit. Set the
    setting explicitly to override, including "memory://" to keep the counters
    per-worker on purpose.
    """
    from buraq.conf import settings

    if storage is None:
        storage = getattr(settings, "RATE_LIMIT_STORAGE", "") or ""
    if storage:
        return storage

    cache_url = getattr(settings, "CACHE_REDIS_URL", None)
    if not cache_url:
        return "memory://"

    # The cache stores its URL for a client of its own; limits needs to be told
    # to use the non-blocking one.
    shared = cache_url if cache_url.startswith("async+") else f"async+{cache_url}"
    if _limits_installed():
        return shared

    # Falling back rather than refusing to start: this is what a project got
    # before it followed the cache at all, so the limit still works -- it just
    # counts per worker. Refusing would turn adding a Redis cache into a
    # startup failure.
    import warnings

    warnings.warn(
        f"RATE_LIMIT_STORAGE is unset and CACHE_REDIS_URL is {cache_url!r}, but "
        f"the `limits` package is not installed, so rate limits are counted per "
        f"worker: N workers admit N times RATE_LIMIT. Install it with "
        f"`pip install buraq[ratelimit-shared]`, or set "
        f"RATE_LIMIT_STORAGE = 'memory://' to make the per-worker count "
        f"deliberate and silence this.",
        RuntimeWarning,
        stacklevel=3,
    )
    return "memory://"


def _limits_installed() -> bool:
    from importlib.util import find_spec

    try:
        return find_spec("limits") is not None
    except (ImportError, ValueError):
        return False


class RateLimiter:
    """Counts limits against one backend, shared by everything that limits.

    ``RATE_LIMIT`` and every ``@ratelimit`` go through one of these, so they
    count the same way and land in the same place.
    """

    def __init__(self, storage: str = "memory://"):
        if storage == "memory://":
            backend = MemoryBackend()

            async def check(rate: Rate, key: str, cost: int = 1) -> Verdict:
                return backend.hit(key, rate, cost)
        else:
            check = _shared_backend(storage)

        # Bound at startup so the request path has no branch to take.
        self.check = check

    async def hit(self, rate: Rate, key: str, cost: int = 1) -> Verdict:
        """Alias for :meth:`check`. The Verdict is falsey when refused."""
        return await self.check(rate, key, cost)


def _shared_backend(storage: str):
    """A counter shared between workers, via ``limits``.

    Only reached when a project sets RATE_LIMIT_STORAGE, so ``limits`` stays an
    optional install rather than something every project carries for a counter
    it keeps in its own process.
    """
    _check_uri(storage)
    try:
        from limits import parse
        from limits.storage import storage_from_string
    except ImportError as exc:
        raise ImproperlyConfigured(
            f"RATE_LIMIT_STORAGE = {storage!r} needs the `limits` package for a "
            f"shared counter. Install it with `pip install limits`, or leave "
            f"RATE_LIMIT_STORAGE at 'memory://' to count in each worker."
        ) from exc

    store = _open(storage_from_string, storage)
    is_async = _is_async(store)
    if is_async:
        from limits.aio.strategies import MovingWindowRateLimiter
    else:
        from limits.strategies import MovingWindowRateLimiter
    limiter = _build(MovingWindowRateLimiter, store, storage)

    # limits parses its own rate strings; ours are already numbers.
    items: dict[Rate, object] = {}

    def item_for(rate: Rate):
        item = items.get(rate)
        if item is None:
            item = items[rate] = parse(f"{rate.amount}/{rate.seconds} second")
        return item

    async def check(rate: Rate, key: str, cost: int = 1) -> Verdict:
        item = item_for(rate)
        if is_async:
            allowed = await limiter.hit(item, key, cost=cost)
            stats = await limiter.get_window_stats(item, key)
        else:
            allowed = limiter.hit(item, key, cost=cost)
            stats = limiter.get_window_stats(item, key)
        reset = max(1, int(stats.reset_time - time.time() + 0.999))
        return Verdict(allowed, rate.amount, max(0, stats.remaining), reset)

    return check


class GlobalRateLimitMiddleware:
    """Reject a client that has exceeded ``RATE_LIMIT``."""

    def __init__(
        self,
        app,
        limit: str = "",
        storage: str = "memory://",
        limiter: RateLimiter | None = None,
    ):
        self.app = app
        # Parsed once at startup rather than on every request.
        self.rate = parse_rate(limit)
        # The application's limiter, so the global limit and every @ratelimit
        # count into one store rather than two that happen to agree.
        self._check = (limiter or RateLimiter(storage)).check

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        verdict = await self._check(self.rate, client_ip(scope))
        if not verdict:
            await _too_many_requests(send, verdict)
            return

        await _with_headers(self.app, scope, receive, send, verdict)


async def _with_headers(app, scope, receive, send, verdict: Verdict) -> None:
    """Pass the response through, adding what is left of the allowance.

    A client that cannot see how much it has left has to discover the limit by
    hitting it. These are the headers everything from GitHub to Stripe sends,
    and neither slowapi nor DRF sends them.
    """
    started = False

    async def send_with_headers(message):
        nonlocal started
        if not started and message["type"] == "http.response.start":
            started = True
            headers = list(message.get("headers", []))
            # A route with its own @ratelimit has already said what *its*
            # allowance is, and that is the one the caller is spending. Adding
            # the global numbers on top would send the header twice, which a
            # client reads as one value joined by a comma.
            if not any(name == b"x-ratelimit-limit" for name, _ in headers):
                message = dict(message)
                message["headers"] = [*headers, *rate_headers(verdict)]
        await send(message)

    await app(scope, receive, send_with_headers)


def rate_headers(verdict: Verdict) -> list[tuple[bytes, bytes]]:
    """The three headers a client needs to pace itself."""
    return [
        (b"x-ratelimit-limit", str(verdict.limit).encode()),
        (b"x-ratelimit-remaining", str(verdict.remaining).encode()),
        (b"x-ratelimit-reset", str(verdict.reset_after).encode()),
    ]


def _is_async(store) -> bool:
    from limits.aio.storage import Storage as AsyncStorage

    return isinstance(store, AsyncStorage)


def _check_uri(uri: str) -> str:
    """Refuse a store that would block the event loop.

    The synchronous clients in ``limits`` do blocking socket I/O, and one of
    those on the request path stalls every request the worker is serving, not
    just this one.
    """
    if uri == "memory://" or uri.startswith("async+"):
        return uri
    raise ImproperlyConfigured(
        f"RATE_LIMIT_STORAGE = {uri!r} would block the event loop on every "
        f"request. Use 'async+{uri}' for the non-blocking client."
    )


def _open(factory, uri: str):
    """Name the package to install, rather than the import that failed."""
    from limits.errors import ConfigurationError

    try:
        return factory(uri)
    except ConfigurationError as exc:
        package = str(exc).split("'")[1].split(".")[0] if "'" in str(exc) else ""
        install = f" Install it with `pip install {package}`." if package else ""
        raise ImproperlyConfigured(
            f"RATE_LIMIT_STORAGE = {uri!r} needs a driver that is not "
            f"installed.{install}"
        ) from exc


def _build(strategy, store, uri: str):
    """Turn a NotImplementedError from `limits` into something a settings file
    can act on: it names the strategy class, not the setting that chose it."""
    try:
        return strategy(store)
    except NotImplementedError as exc:
        raise ImproperlyConfigured(
            f"RATE_LIMIT_STORAGE = {uri!r} cannot count a moving window, which "
            f"is how Buraq applies RATE_LIMIT. Use a store that can: "
            f"'async+redis://...', 'async+mongodb://...', or the default "
            f"'memory://'."
        ) from exc


def client_ip(scope) -> str:
    """The client's address, trusting X-Forwarded-For's first entry when present.

    Behind a proxy every request arrives from the proxy, so limiting on the
    socket address would count the whole site as one client. The header is only
    as trustworthy as whatever sets it, which is why the limit is a coarse
    guard and not an authorisation decision.
    """
    for key, value in scope.get("headers", ()):
        if key == b"x-forwarded-for" and value:
            return value.decode("latin-1").split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else "unknown"


async def _too_many_requests(send, verdict: Verdict) -> None:
    body = b'{"detail":"Rate limit exceeded"}'
    await send({
        "type": "http.response.start",
        "status": 429,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
            # How long to wait, so a client can back off sensibly rather than
            # retrying immediately into the same wall.
            (b"retry-after", str(verdict.reset_after).encode()),
            *rate_headers(verdict),
        ],
    })
    await send({"type": "http.response.body", "body": body})
