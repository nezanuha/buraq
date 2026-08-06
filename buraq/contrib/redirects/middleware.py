"""ASGI middleware that processes database-driven URL redirects on 404."""
from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send


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

        response_sent = False
        captured_status: int | None = None

        async def capture(message):
            nonlocal response_sent, captured_status
            if message["type"] == "http.response.start":
                captured_status = message.get("status", 200)
            if not response_sent:
                await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body"):
                response_sent = True

        await self.app(scope, receive, capture)

        if captured_status == 404:
            path = scope.get("path", "/")
            try:
                from buraq.contrib.redirects.models import Redirect
                rule = await Redirect.objects.get_or_none(old_path=path)
                if rule is not None:
                    location = rule.new_path or ""
                    status = 410 if not location else 301
                    headers = [(b"content-length", b"0")]
                    if location:
                        headers.append((b"location", location.encode()))
                    await send({"type": "http.response.start", "status": status,
                                "headers": headers})
                    await send({"type": "http.response.body", "body": b""})
            except Exception:
                pass
