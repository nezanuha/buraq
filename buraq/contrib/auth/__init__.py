"""
Session-based authentication helpers.

Usage::

    from buraq.contrib.auth import authenticate, login, logout

    async def login_view(request):
        user = await authenticate(request, username="alice", password="secret")
        if user:
            await login(request, user)
            return RedirectResponse("/dashboard")
        ...

    async def logout_view(request):
        await logout(request)
        return RedirectResponse("/")
"""
from __future__ import annotations

import logging

_log = logging.getLogger(__name__)
_AUTH_USER_SESSION_KEY = "_auth_user_id"


# ── Password utilities ────────────────────────────────────────────────────────

def make_password(password: str) -> str:
    """Hash a plain-text password using Argon2."""
    from buraq.core.auth import hash_password
    return hash_password(password)


def check_password(password: str, hashed: str) -> bool:
    """Verify a plain-text password against a stored hash."""
    from buraq.core.auth import verify_password
    return verify_password(password, hashed)


def validate_password(password: str, min_length: int = 8) -> None:
    """
    Raise ValidationError if the password does not meet minimum requirements.

    Rules:
    - At least ``min_length`` characters (default 8)
    - Not entirely numeric
    """
    from buraq.exceptions import ValidationError
    if not password or len(password) < min_length:
        raise ValidationError(
            f"This password is too short. It must contain at least {min_length} characters.",
            code="password_too_short",
        )
    if password.isdigit():
        raise ValidationError(
            "This password is entirely numeric.",
            code="password_entirely_numeric",
        )


async def update_session_auth_hash(request, user) -> None:
    """
    Re-log the user in after a password change so their session is not invalidated.

    Call this after saving a new password to keep the user authenticated.
    """
    session = request.session
    session[_AUTH_USER_SESSION_KEY] = str(user.id)
    request.scope["user"] = user


async def authenticate(request, *, username: str, password: str):
    """
    Verify credentials against all configured ``AUTHENTICATION_BACKENDS``.

    Returns the first ``User`` instance returned by a backend, or ``None``
    if every backend declines or raises.
    """
    from buraq.contrib.auth.backends import _load_backends

    for backend in _load_backends():
        try:
            user = await backend.authenticate(request, username=username, password=password)
        except Exception:
            _log.debug("authenticate(): backend %r raised", backend, exc_info=True)
            continue
        if user is not None:
            user._auth_backend = f"{backend.__class__.__module__}.{backend.__class__.__name__}"
            return user
    return None


async def login(request, user) -> None:
    """
    Persist the authenticated user into the session.

    Cycles the session to prevent session fixation, then writes
    ``_auth_user_id`` so ``AuthenticationMiddleware`` can restore the user
    on subsequent requests.
    """
    session = request.session
    session.cycle_key()
    session[_AUTH_USER_SESSION_KEY] = str(user.id)
    request.scope["user"] = user

    # Update last_login asynchronously (fire-and-forget — don't block the view)
    import asyncio

    from buraq.utils.timezone import now as _now

    async def _update_last_login():
        try:
            user.last_login = _now()
            await user.save(update_fields=["last_login"])
        except Exception:
            _log.debug("login(): could not update last_login for user %r", user.id)

    asyncio.create_task(_update_last_login())


async def logout(request) -> None:
    """
    Remove the authenticated user from the session.

    Flushes the entire session (clears all data and deletes the cookie).
    Sets ``request.user`` to ``AnonymousUser`` immediately.
    """
    from buraq.contrib.auth.models import AnonymousUser
    request.session.flush()
    request.scope["user"] = AnonymousUser()
