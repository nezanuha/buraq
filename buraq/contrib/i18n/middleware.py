"""
LocaleMiddleware — detects the active language for each request.

Detection order:
  1. URL prefix  (e.g. /ar/about)
  2. Cookie      (LANGUAGE_COOKIE_NAME)
  3. Accept-Language header
  4. settings.LANGUAGE_CODE (fallback)

Add to MIDDLEWARE in settings:
    MIDDLEWARE = [
        "buraq.contrib.i18n.middleware.LocaleMiddleware",
        ...
    ]
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from buraq.utils.translation import activate, deactivate

if TYPE_CHECKING:
    from collections.abc import Callable


class LocaleMiddleware:
    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        language = _detect_language(scope)
        token = activate(language)
        try:
            await self.app(scope, receive, send)
        finally:
            deactivate(token)


def _detect_language(scope: dict) -> str:
    from buraq.conf.defaults import settings

    supported: list[str] = [code for code, _ in getattr(settings, "LANGUAGES", [])]
    default: str = getattr(settings, "LANGUAGE_CODE", "en")

    headers: dict[bytes, bytes] = dict(scope.get("headers", []))

    # 1. URL prefix — e.g. /ar/about → "ar"
    path: str = scope.get("path", "")
    if path and path != "/":
        prefix = path.split("/")[1]
        if prefix in supported:
            return prefix

    # 2. Cookie
    cookie_name: str = getattr(settings, "LANGUAGE_COOKIE_NAME", "buraq_language")
    raw_cookie = headers.get(b"cookie", b"").decode()
    for part in raw_cookie.split(";"):
        name, _, value = part.strip().partition("=")
        if name.strip() == cookie_name:
            lang = value.strip()
            if lang in supported:
                return lang

    # 3. Accept-Language header — pick the highest-quality supported language
    accept = headers.get(b"accept-language", b"").decode()
    if accept:
        lang = _parse_accept_language(accept, supported)
        if lang:
            return lang

    return default


def _parse_accept_language(header: str, supported: list[str]) -> str | None:
    """Parse Accept-Language header and return the best supported match."""
    tags: list[tuple[float, str]] = []
    for item in header.split(","):
        item = item.strip()
        if not item:
            continue
        if ";q=" in item:
            lang, _, q = item.partition(";q=")
            try:
                quality = float(q)
            except ValueError:
                quality = 1.0
        else:
            lang = item
            quality = 1.0
        tags.append((quality, lang.strip().lower()))

    tags.sort(reverse=True)

    for _, lang in tags:
        # exact match
        if lang in supported:
            return lang
        # language-only match (e.g. "en-US" → "en")
        base = lang.split("-")[0]
        if base in supported:
            return base

    return None
