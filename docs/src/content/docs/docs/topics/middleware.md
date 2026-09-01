---
title: "Middleware"
description: "Middleware processes every request before it reaches a view and every response before it's sent to the client."
---

Middleware processes every request before it reaches a view and every response before it's sent to the client.

## Built-in middleware

These are the default `MIDDLEWARE`, listed outermost first — the entry at the
top sees a request before every entry below it, and touches the response last:

```python title="config/settings.py"
MIDDLEWARE = [
    "buraq.middleware.security.SecurityMiddleware",
    "buraq.middleware.cors.CORSMiddleware",
    "buraq.contrib.sessions.middleware.SessionMiddleware",
    "buraq.contrib.auth.middleware.AuthenticationMiddleware",
    "buraq.middleware.csrf.CsrfViewMiddleware",
    "buraq.middleware.gzip.GZipMiddleware",
]
```

| Middleware | Purpose |
|---|---|
| Security | `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, HSTS, `ALLOWED_HOSTS` |
| CORS | Cross-Origin Resource Sharing headers |
| Session | Cookie-based sessions |
| Authentication | Reads the session, sets `request.user` (`User` or `AnonymousUser`) |
| CSRF | Rejects an unsafe request without a valid token; `@csrf_exempt` opts a view out |
| GZip | Response compression (see the note below) |

Order matters: `AuthenticationMiddleware` reads `request.session`, so it must be
listed below `SessionMiddleware`.

:::caution[Compression and secrets]
Buraq compresses responses by default; the framework this borrows from ships
compression off and asks you to consider it first. The concern is BREACH: when a
page contains both a secret and text an attacker controls, how well the response
compresses leaks the secret a character at a time.

Buraq's own exposure is closed — the CSRF token is the only secret it renders,
and it is masked so no two responses repeat it. What remains is
application-specific: if one of your own pages renders a stable secret — an API
key, a password-reset token, an invitation code — *and* reflects user input on
the same page, that page is exposed regardless of the framework.

If that describes your application, either stop rendering the secret beside
reflected input, or drop `buraq.middleware.gzip.GZipMiddleware` from
`MIDDLEWARE`. Static files stay compressed either way, because `collectstatic`
compresses them on disk.

The default is on because every CDN and reverse proxy in front of a modern
application compresses too — turning it off in the application alone buys
nothing if Cloudflare or Nginx compresses the same response.
::: Remove an entry and its behaviour goes with it
— a JSON-only API has no use for cookie sessions, and dropping both session and
authentication lines is the way to say so.

## CORS settings

```python
CORS_ORIGINS           = ["https://myfrontend.com", "https://admin.mysite.com"]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS     = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS     = ["*"]
```

:::caution
Leaving `CORS_ORIGINS` empty automatically disables `CORS_ALLOW_CREDENTIALS` — browsers reject credentialed requests to wildcard origins.
:::

## Custom middleware

```python title="myapp/middleware.py"
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RequestTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        import time
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        response.headers["X-Response-Time"] = f"{duration:.3f}s"
        return response
```

Register in your app:

```python title="config/urls.py"
from myapp.middleware import RequestTimingMiddleware

app = Buraq(settings_module="config.settings")
app.add_middleware(RequestTimingMiddleware)
```

## Middleware order

Middleware is applied in reverse registration order — the last one registered is the outermost layer (first to process the request, last to process the response).

`AuthenticationMiddleware` depends on `SessionMiddleware` being present, so register `AuthenticationMiddleware` after `SessionMiddleware`:

```python
from buraq.contrib.auth.middleware import AuthenticationMiddleware
from buraq.contrib.sessions import SessionMiddleware
from buraq.conf import settings

app.add_middleware(AuthenticationMiddleware)   # registered second → runs first
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
```

## CommonMiddleware

`CommonMiddleware` handles two common HTTP concerns:

- **Trailing-slash redirects** — when `APPEND_SLASH = True` (the default), requests for URLs without a trailing slash are redirected to the slash version if the route exists.
- **`Content-Length` header** — automatically adds a `Content-Length` header to responses that don't already have one.

```python title="config/settings.py"
MIDDLEWARE = [
    ...
    "buraq.middleware.common.CommonMiddleware",
]
APPEND_SLASH = True   # default; set False to disable redirect behaviour
```

## BrokenLinkEmailsMiddleware

Sends an email to each address in `MANAGERS` when a 404 response is returned for a request that came from an internal `Referer` (i.e. a broken link on your own site). Silently ignores 404s from external referrers.

```python title="config/settings.py"
MIDDLEWARE = [
    "buraq.middleware.common.CommonMiddleware",
    "buraq.middleware.common.BrokenLinkEmailsMiddleware",   # must come after CommonMiddleware
    ...
]

MANAGERS = [
    ("Alice", "alice@example.com"),
    ("Bob",   "bob@example.com"),
]
```

If `MANAGERS` is empty or unset, the middleware is a no-op. The email includes the broken URL and the referrer so you can fix the link.

## GZipMiddleware

Compresses HTTP responses using gzip when the client sends `Accept-Encoding: gzip`. Only compresses text-based content types above a minimum size threshold.

```python title="config/settings.py"
MIDDLEWARE = [
    ...
    "buraq.middleware.gzip.GZipMiddleware",
]
```

## ConditionalGetMiddleware

Adds `ETag` and `Last-Modified` headers to responses and returns `304 Not Modified` when the browser's conditional headers (`If-None-Match`, `If-Modified-Since`) match, saving bandwidth for unchanged resources.

```python title="config/settings.py"
MIDDLEWARE = [
    ...
    "buraq.middleware.common.ConditionalGetMiddleware",
]
```

## MessageMiddleware

Persists flash messages in the session between requests. Required by `buraq.contrib.messages` and `SuccessMessageMixin`:

```python title="config/settings.py"
MIDDLEWARE = [
    "buraq.contrib.sessions.middleware.SessionMiddleware",
    "buraq.contrib.messages.middleware.MessageMiddleware",   # must come after SessionMiddleware
    ...
]
```

## Rate limiting

`RATE_LIMIT` limits every route by IP; `@ratelimit` tightens it for one. Both go
through a single `RateLimiter`, so they count the same way and share one store.

### Usage

Global limit — every route, by IP:

```python title="config/settings.py"
RATE_LIMIT = "100/minute"   # the default
RATE_LIMIT = ""             # off; @ratelimit still works
```

One route, tighter — `key` defaults to `"ip"`, right for login since there is no
user yet:

```python title="accounts/views.py"
from buraq.decorators import ratelimit


@ratelimit("5/minute")
async def login(request):
    ...


@ratelimit("5/minute", "50/day")     # both apply
async def send_code(request):
    ...
```

By signed-in user — the limit follows them across devices and networks:

```python title="accounts/views.py"
@ratelimit("100/hour", key="user")
async def send_invite(request):
    ...
```

By anything else — API key, tenant, target account:

```python title="api/views.py"
@ratelimit("1000/hour", key=lambda r: r.headers.get("x-api-key", ""))
async def search(request):
    ...
```

Shared across workers — otherwise four workers with `100/minute` admit 400. If
your cache is already Redis, the counters follow it and there is nothing to set:

```python title="config/settings.py"
CACHE_REDIS_URL = "redis://localhost:6379"   # the counters go here too

# only to point them somewhere else, or to keep them per-worker on purpose
RATE_LIMIT_STORAGE = "memory://"
```

Weight an expensive route — `cost` spends more of the allowance per call:

```python title="reports/views.py"
@ratelimit("10/minute", cost=5)     # two calls a minute, not ten
async def export(request):
    ...
```

Skip the limit for some callers — a health check, or staff:

```python title="api/views.py"
@ratelimit("60/minute", exempt=lambda r: r.scope["user"].is_staff)
async def dashboard(request):
    ...
```

Manual, for a key you compute yourself:

```python title="accounts/views.py"
from starlette.responses import JSONResponse

from buraq.ratelimit import parse_rate

ATTEMPTS = parse_rate("5/hour")


async def reset_password(request, email: str):
    if not await request.app.state.limiter.hit(ATTEMPTS, f"reset:{email}"):
        return JSONResponse({"detail": "Too many attempts"}, status_code=429)
```

Over the limit is `429` with `{"detail": "Rate limit exceeded"}` and a
`Retry-After` header, from both paths.

A limited response also carries `X-RateLimit-Limit`, `-Remaining` and `-Reset`,
so a client can pace itself rather than discovering the limit by hitting it.
They describe the limit the caller is actually spending: a route's own
`@ratelimit` where it has one, the global limit elsewhere, and the tightest of
several where a route carries more than one. A route with no limit of its own,
under `RATE_LIMIT = ""`, is not limited and sends none.

The rest of this section is why each of those is shaped the way it is.

### The global limit

When `RATE_LIMIT` is set, Buraq installs `GlobalRateLimitMiddleware` — a small
pure-ASGI middleware that checks the limit and answers `429`. The counter lives
in memory and the check costs about a microsecond, so it is cheap enough to
leave on — enforcement adds single-digit microseconds to a request, whatever the
size of the project.

Set `RATE_LIMIT = ""` if something in front of the application already limits by
IP, as Nginx and every CDN can: the middleware is then not installed at all, and
per-route `@ratelimit` keeps working.

Limit strings are read by `parse_rate`, which takes `5/minute`, `5 per minute`,
`10/5 minutes`, and the `s`/`m`/`h`/`d`/`w` abbreviations, over periods from a
second to a week. The same parser reads `RATE_LIMIT` and `@ratelimit`, so both
take the same spellings, and both reject a malformed one where it is written
rather than at the first request it would have been checked against.

Several limits may be given — `@ratelimit("5/minute", "50/day")` — and all of
them apply. Stacking the decorator accumulates rather than replacing. A limit on
a route is counted separately from the global one and from every other route's;
only the store is shared.

### What counts as one client

`key` decides. It defaults to `"ip"`, resolved by `client_ip()`: the first entry
in `X-Forwarded-For` when that header is present, falling back to the socket
address. Without the header every request behind a proxy would arrive from the
proxy, and one heavy client would lock out everyone sharing it.

:::caution[`X-Forwarded-For` is only as trustworthy as whatever sets it]
Anyone can send that header. Treat a rate limit as a coarse guard against
floods, not as an authorisation decision — and if your proxy does not strip and
rewrite it, limit at the edge instead.
:::

For anything a *signed-in* user does, prefer `key="user"`. An office, a school
or a phone network is one address, so limiting a signed-in action by IP rations
it across everybody there at once. Counting the user also stops one person
resetting their own allowance by changing networks. Anonymous callers have no
identity to count, so `"user"` falls back to their address.

A callable takes the request and returns a string, for limiting by anything else
in it.

### Sharing the count between workers

A counter in the worker process is counted per worker: four of them with
`100/minute` admit up to 400. `RATE_LIMIT_STORAGE` says where the counters go,
and reaches both `RATE_LIMIT` and `@ratelimit`.

It is empty by default, which means **wherever the cache is**. A project running
Redis for its cache has already said where its shared state lives, so the limits
go there and come out correct across workers without naming the same server
twice. With no Redis cache configured, the counters stay in the process and
nothing extra needs to run.

Set it to override:

| Value | Where the counters go | Needs |
| --- | --- | --- |
| *(empty — the default)* | `CACHE_REDIS_URL` if set, else in-process | — |
| `memory://` | in-process, per worker, deliberately | nothing |
| `async+redis://host:6379` | that Redis, not the cache's | `pip install buraq[ratelimit-shared] coredis` |
| `async+mongodb://host:27017` | that MongoDB | `pip install buraq[ratelimit-shared] motor` |

`resolve_storage()` is what works this out, if you want to check what a given
settings file resolves to.

:::caution[Following the cache needs `limits` installed]
The shared counter is handed to [limits](https://limits.readthedocs.io/), an
optional install. If your cache is Redis but `limits` is missing, Buraq warns
and counts per worker rather than refusing to start — adding a Redis cache
should not turn into a startup failure — but N workers then admit N times the
limit. `pip install buraq[ratelimit-shared]` fixes it, and an explicit
`RATE_LIMIT_STORAGE = "memory://"` says the per-worker count is deliberate and
silences the warning.
:::

Why `limits` rather than the cache backend, when the cache is right there:
counting a moving window needs the *times of the hits inside the window*, and a
cache API of `get`/`set`/`incr` cannot express that. Building on it would force a
fixed window — which admits twice the limit across a boundary, the exact flaw
that ruled out SlowAPI. Doing it properly across processes is also where rate
limiters go subtly wrong, and that correctness is worth the optional dependency.
Only the *address* is shared with the cache, not the mechanism.

The `async+` prefix is required for anything over the network. The synchronous
clients in `limits` do blocking socket I/O, and one of those on the request path
stalls every request the worker is serving — not just the one being checked — so
Buraq refuses a URI without it rather than quietly costing you the event loop.

Memcached cannot be used: `RATE_LIMIT` is a moving window, and memcached cannot
read back the timestamps inside one. A missing driver, an unusable store and a
blocking URI are all reported at startup, naming what to install or what to use
instead — not at the first request.

The clients are not bundled, since a project on the default counter should not
have to carry a Redis dependency. Limiting at the edge instead — where there is
only one counter anyway — is the other good answer, and costs the application
nothing.

### Checking a limit yourself

The limiter is on the application as `app.state.limiter`, a `RateLimiter` — the
same one `RATE_LIMIT` and `@ratelimit` use, so a manual check shares their store.
Reach for it when the key is not a property of the caller but of what they are
asking for: password resets per *target account*, as in the last example above,
so that flooding one mailbox does not depend on the sender staying put.

`hit(rate, key)` returns a `Verdict`, which is falsey once that key has spent the
limit and carries `limit`, `remaining` and `reset_after`. Parse the rate once at
import rather than per request, as `@ratelimit` does.

To tell the caller what is left, as the decorator and the global limit both do,
add `rate_headers(verdict)` to the response:

```python
from buraq.middleware.ratelimit import rate_headers

verdict = await request.app.state.limiter.hit(ATTEMPTS, f"reset:{email}")
response = JSONResponse({"sent": bool(verdict)})
for name, value in rate_headers(verdict):
    response.headers[name.decode()] = value.decode()
```

:::note[Why Buraq does not use SlowAPI]
FastAPI has no rate limiting of its own, so this is always a third-party choice.
Buraq used [SlowAPI](https://slowapi.readthedocs.io/) and moved off it, then off
its `limits` dependency for the in-process path as well. The counting now lives
in `buraq.ratelimit` — `parse_rate`, `MemoryBackend`, `Verdict` — so the default
path carries no dependency at all.

Three things ruled SlowAPI out, each measured rather than assumed:

- **Its middleware scanned the routing table on every request.** It finds the
  handler with `_find_route_handler`, which regex-matches the request against
  *every* route and does not stop at the first match. So the cost grew with the
  project — 207 µs of enforcement at five routes, 415 µs at two hundred, for a
  check worth 20 µs. A global limit applies to everything, so there is no
  handler to look up in the first place.
- **Its default strategy is a fixed window,** which admits twice the limit
  across a boundary: five at 11:59:59 and five more at 12:00:00.
- **It cannot use an async store,** so its counters stayed in the worker process
  however they were configured — which matters most on a login endpoint, where
  per-worker counting multiplies a brute-force allowance by the number of
  workers.

Owning the in-process counter then made it 16× faster than the library (1.0 µs
against 16.6 µs), and let it bound its own memory, which matters because the key
is usually the caller's address and an open endpoint sees an unbounded number of
those. Cost of enforcement per request, measured end to end:

| routes | SlowAPI | now |
| --- | --- | --- |
| 5 | 207 µs | 3 µs |
| 50 | 266 µs | 6 µs |
| 200 | 415 µs | 5 µs |

Per-route `@ratelimit` went from 62 µs to 7 µs over the same move.
:::

## CSRF protection

Buraq ships a CSRF middleware that validates tokens on state-changing requests.  Tokens are stored in the session.

### Setup

It is in `MIDDLEWARE` already, so there is nothing to set up:

```python title="config/settings.py"
MIDDLEWARE = [
    ...
    "buraq.middleware.csrf.CsrfViewMiddleware",
]
```

Removing that line turns CSRF protection off everywhere. `CsrfViewMiddleware`
skips validation for safe methods (`GET`, `HEAD`, `OPTIONS`, `TRACE`), and for
a view decorated `@csrf_exempt`.

### Using the token in templates

```python
from buraq.contrib.csrf import get_token

async def my_view(request):
    csrf_token = get_token(request)
    return await render(request, "form.html", {"csrf_token": csrf_token})
```

```html
<form method="post">
  <input type="hidden" name="csrftoken" value="{{ csrf_token }}">
  ...
</form>
```

### Decorators

```python
from buraq.contrib.csrf import csrf_protect, ensure_csrf_cookie

# Force CSRF validation on this view
@csrf_protect
async def payment_view(request):
    ...

# Set the CSRF cookie even if the response wouldn't normally need it
@ensure_csrf_cookie
async def frontend_entry(request):
    ...
```

See [CSRF Protection](csrf.md) for the full reference.
