"""
Server-side session middleware for Buraq.

Stores session data on the server (DB, cache, or file) and issues only a
session-ID cookie to the browser. This enables true server-side session
revocation — delete a session from the store and the user is logged out
immediately on their next request, regardless of cookie TTL.

Configuration::

    # config/settings.py
    SESSION_ENGINE = "buraq.contrib.sessions.backends.db"   # or cache / file
    SESSION_COOKIE_AGE = 1209600  # optional, seconds (default 2 weeks)

    # main.py
    from buraq.contrib.sessions import ServerSessionMiddleware
    app.add_middleware(ServerSessionMiddleware)

Revocation::

    # Force-invalidate any session by its key:
    from buraq.contrib.sessions.server import revoke_session
    await revoke_session(session_key)

    # Or from within a view (e.g. on subscription cancellation):
    if request.session.session_key:
        await request.session.flush()   # clears data + deletes server record
"""
from __future__ import annotations

import importlib
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from buraq.conf import settings

_log = logging.getLogger(__name__)


def _load_backend_class(engine: str):
    from buraq.contrib.sessions.backends.base import SessionBase
    module = importlib.import_module(engine)
    for name in dir(module):
        obj = getattr(module, name)
        if (
            isinstance(obj, type)
            and issubclass(obj, SessionBase)
            and obj is not SessionBase
        ):
            return obj
    raise ImportError(f"No SessionBase subclass found in {engine!r}")


class _ServerSession(dict):
    """
    Sync dict wrapper around an async server-side session backend.

    Views interact with it exactly like a plain dict.  The middleware
    handles the async load/save around the request/response cycle.

    Extra attributes:
        session_key  — read-only; the server-side session ID.
        set_expiry() — override the cookie/store TTL for this session.
        flush()      — clear data and schedule deletion of the store record.
    """

    def __init__(self, data: dict, backend) -> None:
        super().__init__(data)
        self._backend = backend
        self._modified = False
        self._cycle = False

    def __setitem__(self, key, value):
        self._modified = True
        super().__setitem__(key, value)

    def __delitem__(self, key):
        self._modified = True
        super().__delitem__(key)

    @property
    def session_key(self) -> str | None:
        return self._backend.session_key

    def set_expiry(self, seconds: int | None) -> None:
        self._backend.set_expiry(seconds)
        self._modified = True

    def flush(self) -> None:
        self.clear()
        self._modified = True

    def cycle_key(self) -> None:
        self._cycle = True
        self._modified = True


class ServerSessionMiddleware(BaseHTTPMiddleware):
    """
    Server-side session middleware.

    Drop-in replacement for the cookie-based SessionMiddleware when you need
    server-side session revocation (subscription cancellation, bans, etc.).
    """

    def __init__(
        self,
        app,
        session_cookie: str = "sessionid",
        max_age: int | None = None,
        same_site: str = "lax",
        https_only: bool = False,
        domain: str | None = None,
    ) -> None:
        super().__init__(app)
        self.session_cookie = session_cookie
        self.max_age = max_age
        self.same_site = same_site
        self.https_only = https_only
        self.domain = domain
        engine = getattr(
            settings,
            "SESSION_ENGINE",
            "buraq.contrib.sessions.backends.db",
        )
        self._backend_cls = _load_backend_class(engine)

    async def dispatch(self, request: Request, call_next) -> Response:
        session_id = request.cookies.get(self.session_cookie)
        backend = self._backend_cls(session_key=session_id)

        if session_id:
            data = await backend.load()
            if not data:
                # Expired or deleted server-side — treat as new session
                session_id = None
        else:
            data = {}

        session = _ServerSession(data, backend)
        request.scope["session"] = session

        response: Response = await call_next(request)

        session = request.scope.get("session", session)

        if session._modified:
            if session:
                backend._session_cache = dict(session)
                if session._cycle:
                    await backend.cycle_key()
                else:
                    await backend.save()
                max_age = self.max_age or backend.get_expiry_age()
                response.set_cookie(
                    key=self.session_cookie,
                    value=backend.session_key,
                    max_age=max_age,
                    httponly=True,
                    samesite=self.same_site,
                    secure=self.https_only,
                    domain=self.domain,
                )
            else:
                # flush() was called — delete the server record and clear cookie
                if session_id:
                    await backend.delete(session_id)
                response.delete_cookie(self.session_cookie)

        return response


async def revoke_session(session_key: str) -> None:
    """
    Force-invalidate any session by its server-side key.

    Can be called from any async context (e.g. webhook handler, admin action).
    The user will be logged out on their next request.
    """
    engine = getattr(
        settings,
        "SESSION_ENGINE",
        "buraq.contrib.sessions.backends.db",
    )
    backend_cls = _load_backend_class(engine)
    backend = backend_cls(session_key=session_key)
    await backend.delete(session_key)
