# Security Middleware

`buraq.middleware.SecurityMiddleware` injects HTTP security headers on every response.

## Setup

```python
from buraq.middleware.security import SecurityMiddleware

app.add_middleware(SecurityMiddleware)
```

## Settings

| Setting | Default | Description |
|---|---|---|
| `SECURE_HSTS_SECONDS` | `0` | HSTS `max-age` in seconds. `0` = disabled. Set to `31536000` (1 year) in production. |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `False` | Add `includeSubDomains` to HSTS header |
| `SECURE_HSTS_PRELOAD` | `False` | Add `preload` to HSTS header |
| `SECURE_CONTENT_TYPE_NOSNIFF` | `True` | Send `X-Content-Type-Options: nosniff` |
| `SECURE_REFERRER_POLICY` | `"same-origin"` | `Referrer-Policy` header value |
| `SECURE_CROSS_ORIGIN_OPENER_POLICY` | `"same-origin"` | `Cross-Origin-Opener-Policy` header |
| `SECURE_SSL_REDIRECT` | `False` | Redirect all HTTP requests to HTTPS |
| `SECURE_PERMISSIONS_POLICY` | `{}` | Dict of Permissions-Policy directives |
| `X_FRAME_OPTIONS` | `"SAMEORIGIN"` | `X-Frame-Options` value. Set to `""` to disable. |

## Production example

```python
# settings.py (production)
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_PERMISSIONS_POLICY = {
    "camera": "()",
    "microphone": "()",
    "geolocation": "()",
}
```

## Headers emitted

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Cross-Origin-Opener-Policy: same-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

!!! note
    `SECURE_SSL_REDIRECT` issues a permanent 301 redirect. Do not enable it until your HTTPS certificate is fully working — it will lock HTTP users out.
