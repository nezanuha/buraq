"""
Cookie-based signed session middleware — like Django's SessionMiddleware.
Requires: uv add itsdangerous
"""
import json
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_log = logging.getLogger(__name__)


class _SessionDict(dict):
    """A dict that tracks whether it has been modified."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._modified = False

    def __setitem__(self, key, value):
        self._modified = True
        super().__setitem__(key, value)

    def __delitem__(self, key):
        self._modified = True
        super().__delitem__(key)

    def flush(self) -> None:
        """Clear all session data."""
        self._modified = True
        self.clear()

    def cycle_key(self) -> None:
        """Generate a new session key (no-op for cookie sessions)."""
        pass


class SessionMiddleware(BaseHTTPMiddleware):
    """
    Signed cookie session middleware.

    Usage in config/urls.py:
        from buraq.contrib.sessions import SessionMiddleware
        from buraq.conf import settings

        app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

    Usage in views:
        request.session["user_id"] = 42
        uid = request.session.get("user_id")
        del request.session["user_id"]
        request.session.flush()
    """

    def __init__(
        self,
        app,
        secret_key: str,
        session_cookie: str = "session",
        max_age: int = 1209600,  # 2 weeks
        same_site: str = "lax",
        https_only: bool = False,
        domain: str = None,
    ):
        super().__init__(app)
        self.secret_key = secret_key
        self.session_cookie = session_cookie
        self.max_age = max_age
        self.same_site = same_site
        self.https_only = https_only
        self.domain = domain

    async def dispatch(self, request: Request, call_next):
        session_data = self._load(request)
        # Starlette reads request.session from scope["session"] — must use scope,
        # not request.__dict__, so the built-in Request.session property works.
        request.scope["session"] = session_data

        response: Response = await call_next(request)

        # Read back from scope in case a view replaced the session object
        session_data = request.scope.get("session", session_data)

        if session_data._modified:
            if session_data:
                cookie_val = self._dump(dict(session_data))
                response.set_cookie(
                    key=self.session_cookie,
                    value=cookie_val,
                    max_age=self.max_age,
                    httponly=True,
                    samesite=self.same_site,
                    secure=self.https_only,
                    domain=self.domain,
                )
            else:
                # Session was flushed (flush() clears data and sets _modified) — delete cookie
                response.delete_cookie(self.session_cookie)

        return response

    def _load(self, request: Request) -> _SessionDict:
        cookie = request.cookies.get(self.session_cookie, "")
        if not cookie:
            return _SessionDict()
        try:
            from itsdangerous import URLSafeTimedSerializer
            s = URLSafeTimedSerializer(self.secret_key)
            data = s.loads(cookie, max_age=self.max_age)
            if isinstance(data, str):
                data = json.loads(data)
            return _SessionDict(data)
        except Exception:
            _log.debug("Session cookie is invalid or expired — starting a fresh session.")
            return _SessionDict()

    def _dump(self, data: dict) -> str:
        from itsdangerous import URLSafeTimedSerializer
        s = URLSafeTimedSerializer(self.secret_key)
        return s.dumps(data)
