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


def mask_token(secret: str) -> str:
    """
    Disguise the CSRF secret with a fresh random mask.

    Compression plus a secret that repeats in every response is the BREACH
    precondition: an attacker who can get reflected input into a page reads the
    secret a character at a time from how well the response compresses. Masking
    makes the token different in every response, so its compression ratio says
    nothing about the secret underneath.
    """
    raw = bytes.fromhex(secret)
    mask = secrets.token_bytes(len(raw))
    return mask.hex() + bytes(a ^ b for a, b in zip(raw, mask, strict=True)).hex()


def unmask_token(masked: str) -> str:
    """Recover the secret from a masked token, or return it unchanged."""
    try:
        data = bytes.fromhex(masked)
    except ValueError:
        return masked
    if len(data) % 2:
        return masked
    half = len(data) // 2
    mask, payload = data[:half], data[half:]
    return bytes(a ^ b for a, b in zip(payload, mask, strict=True)).hex()


def get_token(request) -> str:
    """
    The CSRF token to put in a response, masked for this request.

    Every call returns a different string for the same underlying secret. What
    is submitted back is unmasked before it is compared.
    """
    return mask_token(_get_or_create_token(request))


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


# The names used on the wire are defined with the middleware, in
# buraq.middleware.csrf, and imported here for the helpers above.
from buraq.middleware.csrf import (  # noqa: E402
    CSRF_COOKIE_NAME,
    CSRF_FIELD_NAME,
    CSRF_HEADER_NAME,
)

__all__ = [
    "get_token", "csrf_protect", "ensure_csrf_cookie", "mask_token", "unmask_token",
    "CSRF_COOKIE_NAME", "CSRF_FIELD_NAME", "CSRF_HEADER_NAME",
]
