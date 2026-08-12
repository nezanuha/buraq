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
        request.scope["user"] = await _get_user(request)
        return await call_next(request)


async def _get_user(request: Request):
    session = getattr(request, "session", None)
    if session is None:
        return AnonymousUser()

    user_id = session.get(_AUTH_USER_SESSION_KEY)
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
