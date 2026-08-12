"""
Per-view cache middleware.

Three middleware classes are provided to mirror the layered cache pattern:

``UpdateCacheMiddleware``
    Inner middleware — runs *after* the view, stores the response in cache.

``FetchFromCacheMiddleware``
    Outer middleware — runs *before* the view, returns a cached response if one exists.

``CacheMiddleware``
    Convenience class that wraps both behaviours into a single middleware.

Usage::

    # Full-site caching (add to MIDDLEWARE list):
    app.add_middleware(CacheMiddleware, cache_timeout=300)

    # Per-view caching (use the @cache_page decorator instead):
    from buraq.contrib.cache.decorators import cache_page

    @cache_page(60)
    async def my_view(request):
        ...
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_CACHE_KEY_PREFIX = "buraq_cache_page:"
_CACHEABLE_METHODS = {"GET", "HEAD"}
_UNCACHEABLE_STATUS = {206, 301, 302, 303, 304, 307, 308, 400, 401, 403, 404, 500}


def _make_cache_key(request: Request) -> str:
    url = str(request.url)
    digest = hashlib.md5(url.encode()).hexdigest()
    return f"{_CACHE_KEY_PREFIX}{digest}"


def _is_cacheable_response(response: Response) -> bool:
    if response.status_code in _UNCACHEABLE_STATUS:
        return False
    cc = response.headers.get("cache-control", "")
    return not ("no-store" in cc or "no-cache" in cc or "private" in cc)


class FetchFromCacheMiddleware(BaseHTTPMiddleware):
    """
    Outer half of the cache middleware pair.

    On every GET/HEAD request it checks the cache; if a stored response
    exists it is returned immediately, bypassing the view.
    """

    def __init__(self, app, cache_alias: str = "default") -> None:
        super().__init__(app)
        self._cache_alias = cache_alias

    def _get_cache(self):
        from buraq.contrib.cache.core import caches
        return caches[self._cache_alias]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method not in _CACHEABLE_METHODS:
            return await call_next(request)

        cache = self._get_cache()
        key = _make_cache_key(request)
        cached = await cache.get(key)
        if cached is not None:
            status, headers, body = cached
            return Response(content=body, status_code=status, headers=dict(headers))

        return await call_next(request)


class UpdateCacheMiddleware(BaseHTTPMiddleware):
    """
    Inner half of the cache middleware pair.

    After the view produces a response it stores the response body in the
    cache so future requests can be served by FetchFromCacheMiddleware.
    """

    def __init__(
        self,
        app,
        cache_timeout: int = 600,
        cache_alias: str = "default",
    ) -> None:
        super().__init__(app)
        self._cache_timeout = cache_timeout
        self._cache_alias = cache_alias

    def _get_cache(self):
        from buraq.contrib.cache.core import caches
        return caches[self._cache_alias]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response: Response = await call_next(request)

        if request.method not in _CACHEABLE_METHODS:
            return response
        if not _is_cacheable_response(response):
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk if isinstance(chunk, bytes) else chunk.encode()

        cache = self._get_cache()
        key = _make_cache_key(request)
        await cache.set(
            key,
            (response.status_code, list(response.headers.items()), body),
            timeout=self._cache_timeout,
        )

        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )


class CacheMiddleware(BaseHTTPMiddleware):
    """
    Full per-view cache middleware — combines fetch + update in one.

    Add to your ASGI app::

        app.add_middleware(CacheMiddleware, cache_timeout=300)

    Or with a named cache alias::

        app.add_middleware(CacheMiddleware, cache_timeout=300, cache_alias="views")
    """

    def __init__(
        self,
        app,
        cache_timeout: int = 600,
        cache_alias: str = "default",
    ) -> None:
        super().__init__(app)
        self._cache_timeout = cache_timeout
        self._cache_alias = cache_alias

    def _get_cache(self):
        from buraq.contrib.cache.core import caches
        return caches[self._cache_alias]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        cache = self._get_cache()

        if request.method in _CACHEABLE_METHODS:
            key = _make_cache_key(request)
            cached = await cache.get(key)
            if cached is not None:
                status, headers, body = cached
                return Response(content=body, status_code=status, headers=dict(headers))

        response: Response = await call_next(request)

        if request.method not in _CACHEABLE_METHODS or not _is_cacheable_response(response):
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk if isinstance(chunk, bytes) else chunk.encode()

        await cache.set(
            key,
            (response.status_code, list(response.headers.items()), body),
            timeout=self._cache_timeout,
        )

        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
