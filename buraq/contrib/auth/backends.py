"""
Authentication backends.

A backend is any class with an ``authenticate`` coroutine and an optional
``get_user`` coroutine.  Buraq tries each backend in
``AUTHENTICATION_BACKENDS`` order and returns the first non-None result.

Usage (custom backend)::

    # config/settings.py
    AUTHENTICATION_BACKENDS = [
        "myapp.backends.LDAPBackend",
        "buraq.contrib.auth.backends.ModelBackend",
    ]

    # myapp/backends.py
    class LDAPBackend:
        async def authenticate(self, request, *, username, password):
            user = ldap_check(username, password)
            return user or None

        async def get_user(self, user_id: int):
            from buraq.contrib.auth.models import User
            return await User.objects.get_or_none(id=user_id)
"""
from __future__ import annotations

_DUMMY_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$"
    "dGVzdHNhbHR2YWx1ZXRlc3Q$"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
)


class ModelBackend:
    """Default backend — checks username + password against the User table."""

    async def authenticate(self, request, *, username: str, password: str):
        import asyncio

        from buraq.contrib.auth._passwords import verify_password
        from buraq.contrib.auth.models import User

        try:
            user = await User.objects.get(username=username)
        except Exception:
            # Run a dummy verify so response time is indistinguishable from a
            # real wrong-password attempt — prevents username enumeration.
            await asyncio.to_thread(verify_password, password, _DUMMY_HASH)
            return None

        if not user.is_active:
            return None

        ok = await asyncio.to_thread(verify_password, password, user.hashed_password)
        if not ok:
            return None

        return user

    async def get_user(self, user_id: int):
        from buraq.contrib.auth.models import User
        return await User.objects.get_or_none(id=user_id)


class AllowAllUsersModelBackend(ModelBackend):
    """
    Like ``ModelBackend`` but authenticates inactive users too.

    Use when you want to allow disabled accounts to authenticate (e.g. to
    show a "your account is disabled" page after login rather than a generic
    "invalid credentials" error).
    """

    async def authenticate(self, request, *, username: str, password: str):
        import asyncio

        from buraq.contrib.auth._passwords import verify_password
        from buraq.contrib.auth.models import User

        try:
            user = await User.objects.get(username=username)
        except Exception:
            await asyncio.to_thread(verify_password, password, _DUMMY_HASH)
            return None

        ok = await asyncio.to_thread(verify_password, password, user.hashed_password)
        return user if ok else None


class AllowAllUsersRemoteUserBackend:
    """
    Remote-user backend that authenticates inactive users.

    Pair with ``RemoteUserMiddleware`` when the upstream server performs
    authentication and you want Buraq to accept the asserted identity even
    for accounts with ``is_active=False``.
    """

    async def authenticate(self, request, *, remote_user: str):
        if not remote_user:
            return None
        from buraq.contrib.auth.models import User
        user, _ = await User.objects.get_or_create(
            username=remote_user,
            defaults={"is_active": True},
        )
        return user

    async def get_user(self, user_id: int):
        from buraq.contrib.auth.models import User
        return await User.objects.get_or_none(id=user_id)


_backend_cache: list | None = None


def _load_backends() -> list:
    """Import and instantiate every backend listed in settings. Result is cached."""
    global _backend_cache
    if _backend_cache is not None:
        return _backend_cache

    import importlib

    from buraq.conf import settings

    backends = []
    for path in settings.AUTHENTICATION_BACKENDS:
        module_path, class_name = path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        backend_cls = getattr(module, class_name)
        backends.append(backend_cls())
    _backend_cache = backends
    return backends


def _clear_backend_cache() -> None:
    """Clear the backend cache — call when AUTHENTICATION_BACKENDS changes at runtime."""
    global _backend_cache
    _backend_cache = None
