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


class ModelBackend:
    """Default backend — checks username + password against the User table."""

    async def authenticate(self, request, *, username: str, password: str):
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
