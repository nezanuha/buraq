"""
View decorators for restricting access based on authentication and permissions.

Usage:
    from buraq.decorators import login_required, staff_required

    @login_required
    async def my_view(request): ...

    @login_required(login_url="/signin")
    async def my_view(request): ...

    @staff_required
    async def admin_view(request): ...

    @cache_control(max_age=3600)
    async def static_view(request): ...
"""
import functools
import logging

from fastapi import HTTPException
from starlette.responses import RedirectResponse

_log = logging.getLogger(__name__)


def login_required(
    view_func=None, login_url: str = "/auth/login", redirect_field_name: str = "next"
):
    """
    Require the user to be authenticated (session-based via AuthenticationMiddleware).
    Redirects to login_url if not authenticated.

    Can be used as:
        @login_required
        @login_required(login_url="/signin")
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(request, *args, **kwargs):
            user = getattr(request, "user", None)
            if not (user and getattr(user, "is_authenticated", False)):
                from urllib.parse import urlencode
                next_url = urlencode({redirect_field_name: str(request.url)})
                return RedirectResponse(
                    url=f"{login_url}?{next_url}",
                    status_code=302,
                )
            return await func(request, *args, **kwargs)
        return wrapper

    if view_func is not None:
        # Used as @login_required (no parens)
        return decorator(view_func)
    return decorator


def staff_required(view_func=None, login_url: str = "/auth/login"):
    """Require is_staff=True. Returns 403 if logged in but not staff."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(request, *args, **kwargs):
            user = getattr(request, "user", None)
            if not (user and getattr(user, "is_authenticated", False)):
                return RedirectResponse(url=login_url, status_code=302)
            if not getattr(user, "is_staff", False):
                raise HTTPException(status_code=403, detail="Staff access required.")
            return await func(request, *args, **kwargs)
        return wrapper

    if view_func is not None:
        return decorator(view_func)
    return decorator


def superuser_required(view_func=None, login_url: str = "/auth/login"):
    """Require is_superuser=True."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(request, *args, **kwargs):
            user = getattr(request, "user", None)
            if not (user and getattr(user, "is_authenticated", False)):
                return RedirectResponse(url=login_url, status_code=302)
            if not getattr(user, "is_superuser", False):
                raise HTTPException(status_code=403, detail="Superuser access required.")
            return await func(request, *args, **kwargs)
        return wrapper

    if view_func is not None:
        return decorator(view_func)
    return decorator


def permission_required(perm: str, login_url: str = "/auth/login", raise_exception: bool = False):
    """
    Require a named permission on the authenticated user.

    Checks ``request.user.has_perm(perm)`` if available; falls back to checking
    ``request.state.user.permissions`` as a set/list.

    Usage:
        @permission_required("posts.add_post")
        async def create_post(request): ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(request, *args, **kwargs):
            user = getattr(request.state, "user", None) or getattr(request, "user", None)
            if user is None:
                if raise_exception:
                    raise HTTPException(status_code=403, detail="Permission denied.")
                return RedirectResponse(url=login_url, status_code=302)

            import inspect as _inspect
            if hasattr(user, "has_perm"):
                if _inspect.iscoroutinefunction(user.has_perm):
                    result = await user.has_perm(perm)
                else:
                    result = user.has_perm(perm)
            else:
                perms = getattr(user, "permissions", []) or []
                result = perm in perms

            if not result:
                if raise_exception:
                    raise HTTPException(status_code=403, detail="Permission denied.")
                return RedirectResponse(url=login_url, status_code=302)

            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


def cache_control(**kwargs):
    """
    Set Cache-Control response headers.

    Usage:
        @cache_control(max_age=3600, public=True)
        async def my_view(request): ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(request, *args, **kw):
            response = await func(request, *args, **kw)
            if hasattr(response, "headers"):
                parts = []
                for key, val in kwargs.items():
                    header_key = key.replace("_", "-")
                    if val is True:
                        parts.append(header_key)
                    elif val is not False:
                        parts.append(f"{header_key}={val}")
                response.headers["Cache-Control"] = ", ".join(parts)
            return response
        return wrapper
    return decorator


def never_cache(func):
    """Set headers to prevent caching."""
    @functools.wraps(func)
    async def wrapper(request, *args, **kwargs):
        response = await func(request, *args, **kwargs)
        if hasattr(response, "headers"):
            response.headers["Cache-Control"] = (
                "max-age=0, no-cache, no-store, must-revalidate, private"
            )
            response.headers["Expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
            response.headers["Pragma"] = "no-cache"
        return response
    return wrapper


def vary_on_headers(*headers):
    """Add Vary header — tells caches the response varies by these request headers."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(request, *args, **kwargs):
            response = await func(request, *args, **kwargs)
            if hasattr(response, "headers"):
                existing = response.headers.get("Vary", "")
                new_vary = ", ".join(filter(None, [existing] + list(headers)))
                response.headers["Vary"] = new_vary
            return response
        return wrapper
    return decorator


def vary_on_cookie(func):
    """Add Vary: Cookie header."""
    return vary_on_headers("Cookie")(func)


def require_http_methods(*methods):
    """
    Restrict a view to specific HTTP methods.

    Usage:
        @require_http_methods("GET", "POST")
        async def my_view(request): ...
    """
    allowed = [m.upper() for m in methods]

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(request, *args, **kwargs):
            if request.method.upper() not in allowed:
                raise HTTPException(
                    status_code=405,
                    detail=f"Method {request.method} not allowed.",
                    headers={"Allow": ", ".join(allowed)},
                )
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


require_GET  = require_http_methods("GET")
require_POST = require_http_methods("POST")
require_safe = require_http_methods("GET", "HEAD")


def csrf_exempt(func):
    """Mark a view as exempt from CSRF protection."""
    func._csrf_exempt = True
    return func


def user_passes_test(test_func, login_url: str = "/auth/login"):
    """
    Decorator that allows access only if ``test_func(user)`` returns True.

    Usage:
        @user_passes_test(lambda u: u.is_staff)
        async def admin_view(request): ...
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        async def wrapper(request, *args, **kwargs):
            user = getattr(request, "user", None)
            result = test_func(user) if user else False
            if not result:
                return RedirectResponse(login_url, status_code=302)
            return await view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def cache_page(timeout: int, *, cache: str = "default", key_prefix: str = ""):
    """
    Cache the full view response for ``timeout`` seconds.

    Uses Buraq's cache backend (memory/Redis/memcached depending on settings).

    Usage:
        @cache_page(60 * 15)   # cache for 15 minutes
        async def article_list(request): ...
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        async def wrapper(request, *args, **kwargs):
            from buraq.contrib.cache.core import cache as _default_cache
            c = _default_cache

            # Build cache key from prefix + method + path + query string
            qs = str(request.url.query) if request.url.query else ""
            prefix = key_prefix or "buraq"
            cache_key = f"{prefix}:page:{request.method}:{request.url.path}:{qs}"

            cached = await c.get(cache_key)
            if cached is not None:
                from starlette.responses import Response
                return Response(
                    content=cached["body"],
                    status_code=cached.get("status", 200),
                    media_type=cached.get("media_type", "text/html"),
                    headers=cached.get("headers", {}),
                )

            response = await view_func(request, *args, **kwargs)

            # Only cache 200 OK responses
            if getattr(response, "status_code", 200) == 200:
                body = b""
                if hasattr(response, "body"):
                    body = response.body
                elif hasattr(response, "render"):
                    body = await response.render()

                # Strip headers that must never be shared across users.
                _UNCACHEABLE_HEADERS = {"set-cookie", "authorization", "www-authenticate"}
                safe_headers = {
                    k: v for k, v in dict(getattr(response, "headers", {})).items()
                    if k.lower() not in _UNCACHEABLE_HEADERS
                }
                await c.set(cache_key, {
                    "body": body,
                    "status": getattr(response, "status_code", 200),
                    "media_type": getattr(response, "media_type", "text/html"),
                    "headers": safe_headers,
                }, timeout=timeout)

            return response
        return wrapper
    return decorator
