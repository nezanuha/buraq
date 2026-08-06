"""ASGI middleware that processes database-driven URL redirects on 404."""
from __future__ import annotations

from urllib.parse import urlparse

from starlette.types import ASGIApp, Receive, Scope, Send


def _is_safe_redirect_path(path: str) -> bool:
    """Return True only if path is a relative URL (no scheme, no netloc)."""
    if not path:
        return False
    parsed = urlparse(path)
    return not parsed.scheme and not parsed.netloc


class RedirectFallbackMiddleware:
    """
    Intercepts 404 responses and checks the Redirect table for a matching rule.

    Add to your application:
        from buraq.contrib.redirects.middleware import RedirectFallbackMiddleware
        app.add_middleware(RedirectFallbackMiddleware)
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Buffer the response so we can decide whether to send it or replace it.
        start_message: dict | None = None
        body_chunks: list[bytes] = []

        async def capture(message):
            nonlocal start_message
            if message["type"] == "http.response.start":
                start_message = message
            elif message["type"] == "http.response.body":
                body_chunks.append(message.get("body", b""))

        await self.app(scope, receive, capture)

        status = start_message.get("status", 200) if start_message else 200

        if status == 404:
            path = scope.get("path", "/")
            try:
                from buraq.contrib.redirects.models import Redirect
                rule = await Redirect.objects.get_or_none(old_path=path)
                if rule is not None:
                    location = rule.new_path or ""
                    if location and not _is_safe_redirect_path(location):
                        location = ""  # refuse unsafe (external) redirect targets
                    redirect_status = 410 if not location else 301
                    headers = [(b"content-length", b"0")]
                    if location:
                        headers.append((b"location", location.encode()))
                    await send({"type": "http.response.start", "status": redirect_status,
                                "headers": headers})
                    await send({"type": "http.response.body", "body": b""})
                    return
            except Exception:
                pass

        # No redirect rule — forward the original buffered response.
        if start_message is not None:
            await send(start_message)
            await send({"type": "http.response.body", "body": b"".join(body_chunks)})
