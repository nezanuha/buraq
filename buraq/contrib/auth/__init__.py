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

async def make_password(password: str) -> str:
    """Hash a plain-text password using Argon2 (runs in a thread — does not block the loop)."""
    import asyncio

    from buraq.contrib.auth._passwords import hash_password
    return await asyncio.to_thread(hash_password, password)


async def check_password(password: str, hashed: str) -> bool:
    """Verify a plain-text password against an Argon2 hash (runs in a thread)."""
    import asyncio

    from buraq.contrib.auth._passwords import verify_password
    return await asyncio.to_thread(verify_password, password, hashed)


from buraq.contrib.auth.password_validation import validate_password  # noqa: E402


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

    task = asyncio.create_task(_update_last_login())
    task.add_done_callback(
        lambda t: t.exception() and _log.debug("login(): _update_last_login failed: %r", t.exception())
    )


async def logout(request) -> None:
    """
    Remove the authenticated user from the session.

    Flushes the entire session (clears all data and deletes the cookie).
    Sets ``request.user`` to ``AnonymousUser`` immediately.
    """
    from buraq.contrib.auth.models import AnonymousUser
    request.session.flush()
    request.scope["user"] = AnonymousUser()


async def get_user(request):
    """
    Return the User instance associated with the current session, or AnonymousUser.

    Called by AuthenticationMiddleware on each request.
    """
    from buraq.contrib.auth.models import AnonymousUser, get_user_model
    user_id = request.session.get(_AUTH_USER_SESSION_KEY)
    if not user_id:
        return AnonymousUser()
    try:
        User = get_user_model()
        user = await User.objects.get_or_none(id=int(user_id))
        return user or AnonymousUser()
    except Exception:
        return AnonymousUser()


class PasswordResetTokenGenerator:
    """
    Generate and verify HMAC-SHA256 tokens for password reset links.

    Usage::

        generator = PasswordResetTokenGenerator()
        token = generator.make_token(user)
        valid = generator.check_token(user, token)
    """

    key_salt = "buraq.contrib.auth.PasswordResetTokenGenerator"
    algorithm = "sha256"

    def _hash_value(self, value: str) -> str:
        import hashlib
        import hmac
        from buraq.conf import settings
        key = f"{self.key_salt}{settings.SECRET_KEY}".encode()
        return hmac.new(key, value.encode(), self.algorithm).hexdigest()

    def _make_hash_value(self, user, timestamp: int) -> str:
        return f"{user.pk}{user.hashed_password}{timestamp}"

    def make_token(self, user) -> str:
        import time
        ts = int(time.time())
        hash_val = self._hash_value(self._make_hash_value(user, ts))
        return f"{ts:x}-{hash_val[:20]}"

    def check_token(self, user, token: str) -> bool:
        import time
        try:
            ts_b36, given_hash = token.split("-", 1)
            ts = int(ts_b36, 16)
        except (ValueError, TypeError):
            return False
        expected = self._hash_value(self._make_hash_value(user, ts))[:20]
        import hmac as _hmac
        if not _hmac.compare_digest(expected, given_hash):
            return False
        # Token valid for PASSWORD_RESET_TIMEOUT seconds (default 3 days)
        try:
            from buraq.conf import settings
            timeout = getattr(settings, "PASSWORD_RESET_TIMEOUT", 259200)
        except Exception:
            timeout = 259200
        return (int(time.time()) - ts) < timeout


default_token_generator = PasswordResetTokenGenerator()
