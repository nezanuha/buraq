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

Buraq wires [SlowAPI](https://slowapi.readthedocs.io/) when it is installed, with
`RATE_LIMIT` as the limit applied to every route:

```python title="config/settings.py"
RATE_LIMIT = "100/minute"     # the default
```

To tighten it for one route, decorate the view:

```python title="accounts/views.py"
from buraq.decorators import ratelimit


@ratelimit("5/minute")
async def login(request):
    ...
```

Several limits may be given — `@ratelimit("5/minute", "50/day")` — and all of
them apply. Stacking the decorator accumulates rather than replacing.

The decorator records the limit and route registration applies it, so a views
module never needs the application object. Reaching the limiter directly would:
the app builds itself by loading `ROOT_URLCONF`, which imports the views, so a
view importing the app back is a circular import and the project does not
start.

Over the limit is `429 Too Many Requests`. Clients are told apart by IP.

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
