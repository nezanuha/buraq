---
title: "CSRF Protection"
description: "Buraq includes CSRF protection utilities to prevent cross-site request forgery attacks."
---

Buraq includes CSRF protection utilities to prevent cross-site request forgery attacks.

## How it works

The CSRF system stores a random token in the user session. On any state-changing request (POST, PUT, PATCH, DELETE), the submitted token is compared to the stored one. Mismatches return a `403 Forbidden`.

## get_token

Return the CSRF token for the current request. Creates one if it doesn't exist yet.

```python
from buraq.contrib.csrf import get_token

async def my_view(request):
    token = get_token(request)
    return await render(request, "form.html", {"csrf_token": token})
```

In templates, include the token as a hidden field:

```html
<form method="post">
  <input type="hidden" name="csrfmiddlewaretoken" value="{{ csrf_token }}">
  ...
</form>
```

## @csrf_protect

Force CSRF validation on a specific view, regardless of middleware settings.

```python
from buraq.contrib.csrf import csrf_protect

@csrf_protect
async def payment_view(request):
    ...
```

Safe methods (GET, HEAD, OPTIONS, TRACE) always pass through without checking.

For AJAX requests, send the token in the `X-CSRFToken` header:

```javascript
fetch("/api/submit", {
  method: "POST",
  headers: { "X-CSRFToken": getCookie("csrftoken") },
  body: JSON.stringify(data),
});
```

## @ensure_csrf_cookie

Set the CSRF cookie on the response even if the view doesn't use the token directly. Useful for single-page apps that need the cookie before making their first POST request.

```python
from buraq.contrib.csrf import ensure_csrf_cookie

@ensure_csrf_cookie
async def home(request):
    return await render(request, "home.html")
```

:::note[Secure flag in production]
When `DEBUG=False`, `ensure_csrf_cookie` automatically sets the `Secure`
flag on the CSRF cookie so it is only transmitted over HTTPS.  No extra
configuration is required.
:::

## CsrfViewMiddleware — stack-level CSRF protection

`CsrfViewMiddleware` is in the default `MIDDLEWARE`, so every unsafe request is
checked unless the view it reaches is decorated `@csrf_exempt`. Nothing needs
adding:

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

It reads the session, so it belongs below `SessionMiddleware`.

:::caution[API clients]
A client that posts JSON has to be issued the token before it can use it: make
one safe request, read the `csrftoken` cookie, and send it back in the
`X-CSRFToken` header on every unsafe request. An endpoint authenticated some
other way — a webhook signature, a bearer token — should be decorated
`@csrf_exempt` rather than made to carry a cookie it has no use for. Removing
the middleware from `MIDDLEWARE` turns the check off everywhere.
:::

### Why the token changes on every page

The value in `{{ csrf_input }}` and the `csrftoken` cookie is different in every
response, even though the secret behind it does not change. That is deliberate.

Buraq compresses responses by default, and compression plus a secret that repeats
in every response is the precondition for BREACH: an attacker who can get
reflected input onto a page learns the secret a character at a time by watching
how well the response compresses. A token that never repeats gives that attack
nothing to measure.

The secret lives in the session; what is rendered is that secret combined with a
fresh random mask, and what is submitted is unmasked before it is compared. Any
token issued for the current session validates, however old.

The two halves of that are exported, for a client that has to mask or compare a
token itself:

```python
from buraq.contrib.csrf import mask_token, unmask_token

masked = mask_token(secret)      # secret -> a value safe to put in a response
secret = unmask_token(masked)    # back again, before comparing
```

`unmask_token` returns its argument unchanged if it is not a masked value, so a
token issued before this existed still compares correctly.

**How it works:**

- Safe methods (`GET`, `HEAD`, `OPTIONS`, `TRACE`) pass through unchecked.
- Unsafe methods (`POST`, `PUT`, `PATCH`, `DELETE`) must supply the CSRF token via:
  - `X-CSRFToken` request header, **or**
  - `csrfmiddlewaretoken` field in the POST body.
- The middleware injects a `Set-Cookie: csrftoken=...` header on every response so JavaScript clients can read the token from the cookie.
- When reading the POST body to find the token, the middleware buffers and replays the body so the view still receives it intact.

```javascript
// Read from cookie, send in header
fetch("/api/submit", {
  method: "POST",
  headers: { "X-CSRFToken": getCookie("csrftoken") },
  body: JSON.stringify(data),
});
```

Use `@csrf_protect` for per-view protection when you prefer not to use the middleware globally.

## @csrf_exempt

Skip CSRF validation for a specific view — typically used for webhooks from third parties.

```python
from buraq.decorators import csrf_exempt

@csrf_exempt
async def stripe_webhook(request):
    payload = await request.json()
    ...
```

## Cookie and field names

| Constant | Default value |
|---|---|
| `CSRF_COOKIE_NAME` | `csrftoken` |
| `CSRF_FIELD_NAME` | `csrfmiddlewaretoken` |
| `CSRF_HEADER_NAME` | `x-csrftoken` |

```python
from buraq.contrib.csrf import CSRF_COOKIE_NAME, CSRF_FIELD_NAME
```
