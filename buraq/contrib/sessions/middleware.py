"""
Cookie-based signed session middleware.
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

    Listed in the MIDDLEWARE setting, where it takes SECRET_KEY and DEBUG from
    settings; pass ``secret_key=`` only to override them.

    Usage in views:
        request.session["user_id"] = 42
        uid = request.session.get("user_id")
        del request.session["user_id"]
        request.session.flush()
    """

    def __init__(
        self,
        app,
        secret_key: str | None = None,
        session_cookie: str | None = None,
        max_age: int | None = None,
        same_site: str | None = None,
        https_only: bool | None = None,
        domain: str = None,
    ):
        super().__init__(app)
        # Both default from settings so the class can be named in MIDDLEWARE and
        # constructed with no arguments, the way every other entry there is.
        from buraq.conf import settings

        self.secret_key = secret_key if secret_key is not None else settings.SECRET_KEY
        self.session_cookie = (
            session_cookie if session_cookie is not None else settings.SESSION_COOKIE_NAME
        )
        self.max_age = max_age if max_age is not None else settings.SESSION_COOKIE_MAX_AGE
        self.same_site = (
            same_site if same_site is not None else settings.SESSION_COOKIE_SAMESITE
        )
        self.http_only = getattr(settings, "SESSION_COOKIE_HTTPONLY", True)
        self.https_only = (
            https_only if https_only is not None else not settings.DEBUG
        )
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
                    httponly=self.http_only,
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
