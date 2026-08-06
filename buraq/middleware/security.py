"""
Security headers middleware.

Add to your application to emit HTTP security headers on every response:

    from buraq.middleware.security import SecurityMiddleware
    app.add_middleware(SecurityMiddleware)

Configure via settings:

    SECURE_HSTS_SECONDS = 31536000          # enable HSTS (0 = off)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True      # X-Content-Type-Options: nosniff
    SECURE_REFERRER_POLICY = "same-origin"  # Referrer-Policy header
    SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
    SECURE_SSL_REDIRECT = False             # redirect HTTP → HTTPS
    SECURE_PERMISSIONS_POLICY = {}          # e.g. {"camera": "()", "microphone": "()"}
    X_FRAME_OPTIONS = "SAMEORIGIN"          # "DENY" | "SAMEORIGIN" | "" (disable)
"""
from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Receive, Scope, Send


class SecurityMiddleware:
    def __init__(self, app: ASGIApp, **options):
        self.app = app
        from buraq.conf import settings

        self._hsts_seconds = int(getattr(settings, "SECURE_HSTS_SECONDS", 0))
        self._hsts_subdomains = bool(getattr(settings, "SECURE_HSTS_INCLUDE_SUBDOMAINS", False))
        self._hsts_preload = bool(getattr(settings, "SECURE_HSTS_PRELOAD", False))
        self._nosniff = bool(getattr(settings, "SECURE_CONTENT_TYPE_NOSNIFF", True))
        self._referrer = getattr(settings, "SECURE_REFERRER_POLICY", "same-origin")
        self._coop = getattr(settings, "SECURE_CROSS_ORIGIN_OPENER_POLICY", "same-origin")
        self._ssl_redirect = bool(getattr(settings, "SECURE_SSL_REDIRECT", False))
        self._permissions = dict(getattr(settings, "SECURE_PERMISSIONS_POLICY", {}))
        self._x_frame = getattr(settings, "X_FRAME_OPTIONS", "SAMEORIGIN")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if self._ssl_redirect:
            scheme = scope.get("scheme", "http")
            if scheme == "http":
                from buraq.conf import settings
                host_raw = dict(scope.get("headers", [])).get(b"host", b"").decode().split(":")[0]
                allowed = settings.ALLOWED_HOSTS
                if allowed != ["*"] and host_raw not in allowed:
                    from starlette.responses import Response
                    bad = Response("Bad Request: invalid Host header.", status_code=400)
                    await bad(scope, receive, send)
                    return
                host = dict(scope.get("headers", [])).get(b"host", b"").decode()
                path = scope.get("path", "/")
                qs = scope.get("query_string", b"").decode()
                url = f"https://{host}{path}"
                if qs:
                    url += f"?{qs}"
                response = _redirect_response(url)
                await response(scope, receive, send)
                return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                self._apply(headers)
            await send(message)

        await self.app(scope, receive, send_with_headers)

    def _apply(self, headers: MutableHeaders) -> None:
        if self._hsts_seconds:
            value = f"max-age={self._hsts_seconds}"
            if self._hsts_subdomains:
                value += "; includeSubDomains"
            if self._hsts_preload:
                value += "; preload"
            headers["Strict-Transport-Security"] = value

        if self._x_frame:
            headers["X-Frame-Options"] = self._x_frame

        if self._nosniff:
            headers["X-Content-Type-Options"] = "nosniff"

        if self._referrer:
            headers["Referrer-Policy"] = self._referrer

        if self._coop:
            headers["Cross-Origin-Opener-Policy"] = self._coop

        if self._permissions:
            policy = ", ".join(f"{k}={v}" for k, v in self._permissions.items())
            headers["Permissions-Policy"] = policy


def _redirect_response(url: str):
    from starlette.responses import RedirectResponse
    return RedirectResponse(url, status_code=301)
