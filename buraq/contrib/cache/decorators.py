import functools
import hashlib
import json
from collections.abc import Callable
from typing import Any

from buraq.contrib.cache.core import cache


def cache_page(timeout: int = 300, key_prefix: str = "page"):
    """
    Cache the full response of a view for `timeout` seconds.
    Cache key is based on the request URL.

    Usage:
        @router.get("/products/")
        @cache_page(timeout=60)
        async def product_list(request: Request):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request: Any | None = kwargs.get("request")
            if request is None:
                for arg in args:
                    if hasattr(arg, "url"):
                        request = arg
                        break

            cache_key = (
                f"{key_prefix}:{request.url}" if request else f"{key_prefix}:{func.__name__}"
            )
            cached = await cache.get(cache_key)
            if cached is not None:
                return cached

            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, timeout)
            return result

        return wrapper
    return decorator


def cache_result(key: str | None = None, timeout: int = 300):
    """
    Cache the return value of any async function.
    Cache key is auto-generated from function name + args if not provided.

    Usage:
        @cache_result(timeout=120)
        async def get_user_stats(user_id: int):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if key:
                cache_key = key
            else:
                payload = [str(a) for a in args] + [f"{k}={v}" for k, v in kwargs.items()]
                arg_hash = hashlib.md5(json.dumps(payload).encode()).hexdigest()[:8]
                cache_key = f"fn:{func.__module__}.{func.__name__}:{arg_hash}"

            cached = await cache.get(cache_key)
            if cached is not None:
                return cached

            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, timeout)
            return result

        return wrapper
    return decorator
