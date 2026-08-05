"""
CSRF utilities — get_token, csrf_protect decorator, ensure_csrf_cookie decorator.

The CSRF middleware in buraq.middleware.csrf handles automatic protection.
These helpers let you manage CSRF tokens in views manually.

Usage:
    from buraq.contrib.csrf import get_token, csrf_protect, ensure_csrf_cookie

    async def my_view(request):
        token = get_token(request)
        return render(request, "form.html", {"csrf_token": token})

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
            response.set_cookie(
                CSRF_COOKIE_NAME,
                token,
                httponly=False,
                samesite="lax",
            )
        return response
    return wrapper


__all__ = [
    "get_token", "csrf_protect", "ensure_csrf_cookie",
    "CSRF_COOKIE_NAME", "CSRF_FIELD_NAME", "CSRF_HEADER_NAME",
]
