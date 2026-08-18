---
title: "Middleware"
description: "Middleware processes every request before it reaches a view and every response before it's sent to the client."
---

Middleware processes every request before it reaches a view and every response before it's sent to the client.

## Built-in middleware

Buraq automatically applies these (configured via settings):

| Middleware | Purpose |
|---|---|
| CORS | Cross-Origin Resource Sharing headers |
| GZip | Response compression |
| Session | Cookie-based sessions |
| Authentication | Reads session, sets `request.user` (`User` or `AnonymousUser`) |
| Security headers | `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, etc. |

## CORS settings

```python
CORS_ALLOW_ORIGINS     = ["https://myfrontend.com", "https://admin.mysite.com"]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS     = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS     = ["*"]
```

:::caution
Setting `CORS_ALLOW_ORIGINS = ["*"]` automatically disables `CORS_ALLOW_CREDENTIALS` — browsers reject credentialed requests to wildcard origins.
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
    "buraq.middleware.common.MessageMiddleware",   # must come after SessionMiddleware
    ...
]
```

## Rate limiting

Buraq includes SlowAPI rate limiting:

```python
from buraq.contrib.ratelimit import limiter, RateLimitExceeded
from starlette.requests import Request


@limiter.limit("5/minute")
async def login(request: Request):
    ...
```

## CSRF protection

Buraq ships a CSRF middleware that validates tokens on state-changing requests.  Tokens are stored in the session.

### Setup

```python title="config/urls.py"
from buraq.contrib.csrf import CSRFMiddleware

app.add_middleware(CSRFMiddleware)
```

`CSRFMiddleware` skips validation for safe methods (`GET`, `HEAD`, `OPTIONS`, `TRACE`).

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
