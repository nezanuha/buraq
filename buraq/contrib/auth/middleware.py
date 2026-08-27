"""
AuthenticationMiddleware — reads _auth_user_id from session, fetches User,
sets request.user (scope["user"]).

Must be added AFTER SessionMiddleware in the middleware stack:
    app.add_middleware(AuthenticationMiddleware)
    app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
"""
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from buraq.contrib.auth.models import AnonymousUser

_log = logging.getLogger(__name__)
_AUTH_USER_SESSION_KEY = "_auth_user_id"



def _static_prefixes() -> tuple[str, ...]:
    """The mount points whose responses are files, never views."""
    from buraq.conf import settings

    prefixes = [
        (getattr(settings, "STATIC_URL", "") or "").rstrip("/"),
        (getattr(settings, "MEDIA_URL", "") or "").rstrip("/"),
        # The admin's own assets, mounted whether or not the project has any.
        "/_buraq/static",
    ]
    return tuple(p for p in prefixes if p)


def _serves_a_file(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in _static_prefixes())


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Reads ``request.session["_auth_user_id"]``, fetches the corresponding
    ``User``, and sets ``request.user``.  Falls back to ``AnonymousUser``
    when the session has no user ID or the user is not found / inactive.

    Usage in settings / application setup::

        from buraq.contrib.auth.middleware import AuthenticationMiddleware
        from buraq.contrib.sessions import SessionMiddleware

        app.add_middleware(AuthenticationMiddleware)
        app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
    """

    async def dispatch(self, request: Request, call_next):
        if _serves_a_file(request.scope.get("path", "")):
            # Nothing under a static or media mount can read request.user, and in
            # development Buraq serves those itself -- so a page with twenty
            # assets was twenty user lookups for a logged-in visitor.
            request.scope["user"] = AnonymousUser()
        else:
            request.scope["user"] = await _get_user(request)
        return await call_next(request)


def _user_id_from_token(request) -> str | None:
    """
    The subject of a bearer token or ``access_token`` cookie, if either verifies.

    Verification is HMAC over the token -- no database, no I/O -- so a request
    that carries a token but no session costs nothing until the user is loaded.
    """
    from buraq.contrib.auth.tokens import TokenError, decode_token

    header = request.headers.get("authorization", "")
    token = ""
    if header[:7].lower() == "bearer ":
        token = header[7:].strip()
    if not token:
        token = request.cookies.get("access_token", "")
    if not token:
        return None

    try:
        return decode_token(token).get("sub")
    except TokenError as exc:
        _log.debug("AuthenticationMiddleware: rejecting token (%s)", exc)
        return None
    except Exception:
        # A misconfigured SECRET_KEY or JWT_ALGORITHM should not take the site
        # down; the request simply carries no identity.
        _log.exception("AuthenticationMiddleware: could not read token")
        return None


async def _get_user(request: Request):
    session = getattr(request, "session", None)
    user_id = session.get(_AUTH_USER_SESSION_KEY) if session is not None else None
    if not user_id:
        user_id = _user_id_from_token(request)
    if not user_id:
        return AnonymousUser()

    try:
        from buraq.contrib.auth.models import User
        from buraq.orm.manager import DoesNotExist
        user = await User.objects.get(id=int(user_id))
        if not user.is_active:
            return AnonymousUser()
        return user
    except (DoesNotExist, ValueError):
        _log.debug("AuthenticationMiddleware: user %r not found — returning AnonymousUser", user_id)
        return AnonymousUser()
    except Exception:
        _log.exception("AuthenticationMiddleware: unexpected error fetching user %r", user_id)
        return AnonymousUser()
