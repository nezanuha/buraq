"""
Cache decorators — re-exported from the canonical implementation in buraq.decorators.

Import from here for convenience:
    from buraq.contrib.cache.decorators import cache_page, cache_result, never_cache
"""
import functools
import hashlib
import json
from collections.abc import Callable

from buraq.contrib.cache.core import cache
from buraq.decorators import cache_page, never_cache  # noqa: F401


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
                encoded = json.dumps(payload).encode()
                arg_hash = hashlib.md5(encoded, usedforsecurity=False).hexdigest()[:8]
                cache_key = f"fn:{func.__module__}.{func.__name__}:{arg_hash}"

            cached = await cache.get(cache_key)
            if cached is not None:
                return cached

            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, timeout)
            return result

        return wrapper
    return decorator
