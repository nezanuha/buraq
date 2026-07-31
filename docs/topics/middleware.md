# Middleware

Middleware processes every request before it reaches a view and every response before it's sent to the client.

## Built-in middleware

Buraq automatically applies these (configured via settings):

| Middleware | Purpose |
|---|---|
| CORS | Cross-Origin Resource Sharing headers |
| GZip | Response compression |
| Session | Cookie-based sessions |
| Security headers | `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, etc. |

## CORS settings

```python
CORS_ALLOW_ORIGINS     = ["https://myfrontend.com", "https://admin.mysite.com"]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS     = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS     = ["*"]
```

!!! warning
    Setting `CORS_ALLOW_ORIGINS = ["*"]` automatically disables `CORS_ALLOW_CREDENTIALS` — browsers reject credentialed requests to wildcard origins.

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

Middleware is applied in reverse registration order — the last one registered is the outermost layer (first to process the request, last to process the response). Register middleware that must run first (e.g., authentication) last.

## Rate limiting

Buraq includes SlowAPI rate limiting:

```python
from buraq.contrib.ratelimit import limiter, RateLimitExceeded
from starlette.requests import Request


@limiter.limit("5/minute")
async def login(request: Request):
    ...
```
