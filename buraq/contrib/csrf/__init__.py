"""
CSRF utilities — get_token, csrf_protect decorator, ensure_csrf_cookie decorator.

Buraq's CSRF protection is opt-in via @csrf_protect on individual views.
Use ensure_csrf_cookie on views that need the token pre-set for AJAX clients.

Usage:
    from buraq.contrib.csrf import get_token, csrf_protect, ensure_csrf_cookie

    async def my_view(request):
        token = get_token(request)
        return await render(request, "form.html", {"csrf_token": token})

    @csrf_protect
    async def sensitive_view(request):
        ...

    @ensure_csrf_cookie
    async def cookie_view(request):
        ...
"""
from __future__ import annotations

import functools
import secrets

CSRF_COOKIE_NAME = "csrftoken"
CSRF_HEADER_NAME = "x-csrftoken"
CSRF_FIELD_NAME = "csrfmiddlewaretoken"


def _get_or_create_token(request) -> str:
    session = getattr(request, "session", None)
    if session is not None:
        token = session.get("_csrf_token")
        if token:
            return token
        token = secrets.token_hex(32)
        session["_csrf_token"] = token
        return token
    token = request.scope.get("_csrf_token")
    if not token:
        token = secrets.token_hex(32)
        request.scope["_csrf_token"] = token
    return token


def get_token(request) -> str:
    """Return the CSRF token for the current request, creating one if needed."""
    return _get_or_create_token(request)


def csrf_protect(func):
    """
    Enforce CSRF validation on a view.

    Safe methods (GET, HEAD, OPTIONS, TRACE) pass through unchecked.
    All others must supply the token via ``X-CSRFToken`` header or
    ``csrfmiddlewaretoken`` POST field.
    """
    @functools.wraps(func)
    async def wrapper(request, *args, **kwargs):
        if request.method.upper() in ("GET", "HEAD", "OPTIONS", "TRACE"):
            return await func(request, *args, **kwargs)

        session = getattr(request, "session", None)
        stored = session.get("_csrf_token") if session else request.scope.get("_csrf_token")

        token = request.headers.get(CSRF_HEADER_NAME)
        if not token:
            try:
                form = await request.form()
                token = form.get(CSRF_FIELD_NAME, "")
            except Exception:
                token = ""

        if not stored or not secrets.compare_digest(stored, token):
            from starlette.responses import Response
            return Response("CSRF verification failed.", status_code=403)

        return await func(request, *args, **kwargs)
    return wrapper


def ensure_csrf_cookie(func):
    """
    Ensure the CSRF cookie is set on every response from this view.

    Use on views that render forms via AJAX or need the cookie pre-set
    before the user submits.
    """
    @functools.wraps(func)
    async def wrapper(request, *args, **kwargs):
        token = get_token(request)
        response = await func(request, *args, **kwargs)
        if hasattr(response, "set_cookie"):
            from buraq.conf import settings
            response.set_cookie(
                CSRF_COOKIE_NAME,
                token,
                httponly=False,
                samesite="lax",
                secure=not settings.DEBUG,
            )
        return response
    return wrapper


class CsrfViewMiddleware:
    """
    Full CSRF middleware for use in the MIDDLEWARE stack.

    Validates POST/PUT/PATCH/DELETE requests against the CSRF token stored in
    the session or scope.  Sets the ``csrftoken`` cookie on every response so
    that JavaScript clients can read the token.

    Usage::

        MIDDLEWARE = [
            ...
            "buraq.contrib.csrf.CsrfViewMiddleware",
        ]
    """

    SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET").upper()
        request_headers = {k.lower(): v for k, v in scope.get("headers", [])}

        # Retrieve stored token from scope (session middleware populates scope["session"])
        session = scope.get("session") or {}
        stored = session.get("_csrf_token") or scope.get("_csrf_token")

        if method not in self.SAFE_METHODS:
            token = request_headers.get(CSRF_HEADER_NAME.encode(), b"").decode()
            if not token:
                # Check POST body
                body_bytes = b""
                more_body = True
                buffered = []
                while more_body:
                    message = await receive()
                    buffered.append(message)
                    body_bytes += message.get("body", b"")
                    more_body = message.get("more_body", False)

                import urllib.parse
                try:
                    fields = dict(urllib.parse.parse_qsl(body_bytes.decode()))
                    token = fields.get(CSRF_FIELD_NAME, "")
                except Exception:
                    token = ""

                # Replay body for the view
                idx = 0
                async def replay_receive():
                    nonlocal idx
                    if idx < len(buffered):
                        msg = buffered[idx]
                        idx += 1
                        return msg
                    return {"type": "http.disconnect"}
                receive = replay_receive

            if not stored or not secrets.compare_digest(stored, token):
                await send({
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [(b"content-type", b"text/plain")],
                })
                await send({"type": "http.response.body", "body": b"CSRF verification failed."})
                return

        # Generate / refresh token for this request
        if not stored:
            stored = secrets.token_hex(32)
            scope["_csrf_token"] = stored

        # Capture response to inject Set-Cookie header

        async def send_with_cookie(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                try:
                    from buraq.conf import settings
                    secure = not settings.DEBUG
                except Exception:
                    secure = False
                cookie = (
                    f"{CSRF_COOKIE_NAME}={stored}; Path=/; SameSite=Lax"
                    + ("; Secure" if secure else "")
                )
                headers.append((b"set-cookie", cookie.encode()))
                await send({**message, "headers": headers})
            else:
                await send(message)

        await self.app(scope, receive, send_with_cookie)


__all__ = [
    "get_token", "csrf_protect", "ensure_csrf_cookie", "CsrfViewMiddleware",
    "CSRF_COOKIE_NAME", "CSRF_FIELD_NAME", "CSRF_HEADER_NAME",
]
