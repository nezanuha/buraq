"""
CommonMiddleware — APPEND_SLASH and PREPEND_WWW support.

ConditionalGetMiddleware — ETag / Last-Modified / 304 support.

MessageMiddleware — placeholder (message storage is handled by contrib.messages).

Usage::

    MIDDLEWARE = [
        ...
        "buraq.middleware.common.CommonMiddleware",
        "buraq.middleware.common.ConditionalGetMiddleware",
    ]
"""
from __future__ import annotations

import hashlib


class CommonMiddleware:
    """
    Handles APPEND_SLASH and PREPEND_WWW settings.

    - ``APPEND_SLASH=True`` (default): redirects URLs missing a trailing slash
      to the slash version, **only** if the original path is not registered.
    - ``PREPEND_WWW=True``: redirects ``example.com`` to ``www.example.com``.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        try:
            from buraq.conf import settings
            append_slash = getattr(settings, "APPEND_SLASH", True)
            prepend_www = getattr(settings, "PREPEND_WWW", False)
        except Exception:
            append_slash = True
            prepend_www = False

        path: str = scope.get("path", "/")
        headers = dict(scope.get("headers", []))
        host: str = headers.get(b"host", b"").decode()

        # PREPEND_WWW
        if prepend_www and host and not host.startswith("www."):
            new_url = f"http{'s' if scope.get('scheme') == 'https' else ''}://www.{host}{path}"
            if scope.get("query_string"):
                new_url += "?" + scope["query_string"].decode()
            await _redirect(send, new_url)
            return

        # APPEND_SLASH
        if append_slash and not path.endswith("/") and "." not in path.rsplit("/", 1)[-1]:
            new_path = path + "/"
            from buraq.urls import _route_registry
            # Only when a route genuinely exists at the slashed path. The old
            # test also matched routes registered *without* the slash, which is
            # every route Buraq has -- so it redirected to an address Starlette's
            # own redirect_slashes immediately sent back, forever.
            if any(rp == new_path for rp in _route_registry.values()):
                new_url = new_path
                if scope.get("query_string"):
                    new_url += "?" + scope["query_string"].decode()
                await _redirect(send, new_url, status=301)
                return

        await self.app(scope, receive, send)


class ConditionalGetMiddleware:
    """
    Adds ETag / Last-Modified headers and returns 304 Not Modified
    when the client's conditional headers match.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        body_chunks: list[bytes] = []
        initial: dict = {}

        async def capture(message):
            if message["type"] == "http.response.start":
                initial["status"] = message["status"]
                initial["headers"] = list(message.get("headers", []))
            elif message["type"] == "http.response.body":
                body_chunks.append(message.get("body", b""))

        await self.app(scope, receive, capture)

        if initial.get("status", 200) != 200:
            await send({"type": "http.response.start", **initial})
            await send({"type": "http.response.body", "body": b"".join(body_chunks)})
            return

        body = b"".join(body_chunks)
        etag = f'"{hashlib.md5(body).hexdigest()}"'

        request_headers = {k.lower(): v for k, v in scope.get("headers", [])}
        if_none_match = request_headers.get(b"if-none-match", b"").decode()
        if if_none_match and etag.strip('"') in if_none_match:
            await send({"type": "http.response.start", "status": 304, "headers": []})
            await send({"type": "http.response.body", "body": b""})
            return

        headers = [h for h in initial.get("headers", []) if h[0].lower() != b"etag"]
        headers.append((b"etag", etag.encode()))
        await send({
            "type": "http.response.start",
            "status": initial.get("status", 200),
            "headers": headers,
        })
        await send({"type": "http.response.body", "body": body})


class BrokenLinkEmailsMiddleware:
    """
    Send an email to ``MANAGERS`` when a 404 response is returned for an
    incoming ``Referer`` that is on the same site (i.e. an internal broken link).

    Register after ``CommonMiddleware`` so slash-redirect 301s are already
    resolved before this middleware evaluates the response status:

    .. code-block:: python

        MIDDLEWARE = [
            "buraq.middleware.common.CommonMiddleware",
            "buraq.middleware.common.BrokenLinkEmailsMiddleware",
            ...
        ]

    Set ``MANAGERS`` in settings to a list of ``("Name", "email@example.com")``
    tuples. If ``MANAGERS`` is empty, the middleware is a no-op.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        initial: dict = {}

        async def capture(message):
            if message["type"] == "http.response.start":
                initial["status"] = message["status"]
                initial["headers"] = list(message.get("headers", []))
            await send(message)

        await self.app(scope, receive, capture)

        if initial.get("status") == 404:
            request_headers = {k.lower(): v for k, v in scope.get("headers", [])}
            referer = request_headers.get(b"referer", b"").decode()
            if referer:
                self._maybe_email(scope, referer)

    def _maybe_email(self, scope, referer: str) -> None:
        try:
            from buraq.conf import settings
            managers = getattr(settings, "MANAGERS", [])
            if not managers:
                return
            from buraq.contrib.email.send import send_mail
            path = scope.get("path", "")
            subject = f"Broken link on {path}"
            body = (
                f"A broken link was detected.\n\n"
                f"Referrer: {referer}\n"
                f"Requested URL: {path}\n"
            )
            import asyncio
            for _name, addr in managers:
                asyncio.ensure_future(send_mail(subject, body, recipient_list=[addr]))
        except Exception:
            pass


async def _redirect(send, location: str, status: int = 302) -> None:
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"location", location.encode())],
    })
    await send({"type": "http.response.body", "body": b""})

