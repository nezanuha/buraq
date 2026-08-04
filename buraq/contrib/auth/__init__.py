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


async def authenticate(request, *, username: str, password: str):
    """
    Verify credentials.  Returns the ``User`` instance on success, or ``None``.

    Checks ``is_active``; inactive accounts always fail.
    """
    from buraq.contrib.auth.models import User
    from buraq.core.auth import verify_password

    try:
        user = await User.objects.get(username=username)
    except Exception:
        return None

    if not user.is_active:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user


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
