"""CSRF protection middleware.

Core middleware rather than part of the csrf contrib app: a project does not
install CSRF the way it installs an app, it turns it on for every view at once.
The token helpers a view or template reaches for -- ``get_token``,
``csrf_protect``, ``ensure_csrf_cookie`` -- stay in :mod:`buraq.contrib.csrf`.
"""

import secrets

#: Names on the wire: the cookie the middleware sets, the header a JavaScript
#: client echoes it back in, and the form field a template renders.
CSRF_COOKIE_NAME = "csrftoken"
CSRF_HEADER_NAME = "x-csrftoken"
CSRF_FIELD_NAME = "csrfmiddlewaretoken"

def _is_exempt(scope) -> bool:
    """
    Whether the view this request will reach is marked ``@csrf_exempt``.

    The middleware runs before routing, so it has to resolve the route itself to
    find out. Without this the decorator exists but does nothing once the
    middleware is in the stack, which leaves a project no way to exempt the one
    endpoint that needs it -- a webhook, or an API authenticated by a bearer
    token rather than a cookie.
    """
    from starlette.routing import Match

    app = scope.get("app")
    for route in getattr(app, "routes", None) or ():
        try:
            match, _ = route.matches(scope)
        except Exception:
            continue
        if match != Match.FULL:
            continue
        endpoint = getattr(route, "endpoint", None)
        # functools.wraps copies __dict__, so the flag survives the wrappers
        # Buraq puts between the route and the view the user wrote.
        return bool(getattr(endpoint, "_csrf_exempt", False))
    return False


class CsrfViewMiddleware:
    """
    Full CSRF middleware for use in the MIDDLEWARE stack.

    Validates POST/PUT/PATCH/DELETE requests against the CSRF token stored in
    the session or scope.  Sets the ``csrftoken`` cookie on every response so
    that JavaScript clients can read the token.

    Usage::

        MIDDLEWARE = [
            ...
            "buraq.contrib.csrf.CsrfViewMiddleware",
        ]
    """

    SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET").upper()
        request_headers = {k.lower(): v for k, v in scope.get("headers", [])}

        # SessionMiddleware puts the live session dict on the scope. Keep the
        # reference rather than falling back to a fresh {}: a new session is
        # empty, which is falsy, and `or {}` would swap in a throwaway that the
        # token could never be written back through.
        session = scope.get("session")
        stored = (session or {}).get("_csrf_token") or scope.get("_csrf_token")

        if method not in self.SAFE_METHODS and not _is_exempt(scope):
            token = request_headers.get(CSRF_HEADER_NAME.encode(), b"").decode()
            if not token:
                # Check POST body
                body_bytes = b""
                more_body = True
                buffered = []
                while more_body:
                    message = await receive()
                    buffered.append(message)
                    body_bytes += message.get("body", b"")
                    more_body = message.get("more_body", False)

                import urllib.parse
                try:
                    fields = dict(urllib.parse.parse_qsl(body_bytes.decode()))
                    token = fields.get(CSRF_FIELD_NAME, "")
                except Exception:
                    token = ""

                # Replay body for the view
                idx = 0
                async def replay_receive():
                    nonlocal idx
                    if idx < len(buffered):
                        msg = buffered[idx]
                        idx += 1
                        return msg
                    return {"type": "http.disconnect"}
                receive = replay_receive

            from buraq.contrib.csrf import unmask_token

            # What arrives is masked -- a different string each render, so its
            # size in a compressed response says nothing about the secret.
            submitted = unmask_token(token) if token else ""
            if not stored or not secrets.compare_digest(stored, submitted):
                await send({
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [(b"content-type", b"text/plain")],
                })
                await send({"type": "http.response.body", "body": b"CSRF verification failed."})
                return

        # Generate / refresh token for this request
        if not stored:
            stored = secrets.token_hex(32)
            if session is None:
                # No session middleware: the token lives for this request only,
                # which is enough for a client that reads the cookie and echoes
                # it straight back on the same connection.
                scope["_csrf_token"] = stored
            else:
                # Persist it, or the cookie carries a token the next request
                # cannot check against and every POST is rejected.
                session["_csrf_token"] = stored

        # Capture response to inject Set-Cookie header

        async def send_with_cookie(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                try:
                    from buraq.conf import settings
                    secure = not settings.DEBUG
                except Exception:
                    secure = False
                from buraq.contrib.csrf import mask_token

                # Masked like the form field: a client reads this cookie and
                # echoes it back, so it must survive unmasking the same way.
                cookie = (
                    f"{CSRF_COOKIE_NAME}={mask_token(stored)}; Path=/; SameSite=Lax"
                    + ("; Secure" if secure else "")
                )
                headers.append((b"set-cookie", cookie.encode()))
                await send({**message, "headers": headers})
            else:
                await send(message)

        await self.app(scope, receive, send_with_cookie)


__all__ = [
    "CsrfViewMiddleware",
    "CSRF_COOKIE_NAME",
    "CSRF_HEADER_NAME",
    "CSRF_FIELD_NAME",
]
