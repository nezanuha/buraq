"""
Decorator utilities — method_decorator for wrapping function decorators on class-based views.

Usage:
    from buraq.utils.decorators import method_decorator
    from buraq.decorators import login_required

    @method_decorator(login_required, name="get")
    class MyView(View):
        async def get(self, request):
            ...

    # Or apply to all HTTP methods via dispatch:
    @method_decorator(login_required, name="dispatch")
    class MyView(View):
        ...
"""
from __future__ import annotations

import asyncio
import contextlib
import functools
from collections.abc import Callable


def method_decorator(decorator: Callable, name: str = "") -> Callable:
    """
    Convert a function decorator into a class-based view decorator.

    When ``name`` is given, only that method on the view class is wrapped.
    When omitted, the class's ``dispatch`` method is wrapped (affects all methods).

    Usage:
        @method_decorator(login_required, name="dispatch")
        class MyView(View):
            async def get(self, request): ...
    """
    def _dec(obj):
        if isinstance(obj, type):
            # Applied to a class
            method_name = name or "dispatch"
            original = getattr(obj, method_name, None)
            if original is None:
                raise ValueError(
                    f"{obj.__name__} has no method {method_name!r}. "
                    f"Available: {[m for m in dir(obj) if not m.startswith('_')]}"
                )
            wrapped = _wrap_method(decorator, original)
            setattr(obj, method_name, wrapped)
            return obj
        else:
            # Applied to a method/function directly
            return _wrap_method(decorator, obj)

    functools.update_wrapper(_dec, decorator)
    return _dec


def _wrap_method(decorator: Callable, method: Callable) -> Callable:
    """Apply a function decorator to a (possibly async) method."""
    if asyncio.iscoroutinefunction(method):
        # Build a sync wrapper that the decorator can process,
        # then re-wrap the result to be async.
        @functools.wraps(method)
        def sync_placeholder(*args, **kwargs):
            raise RuntimeError("Use the async version")

        decorated = decorator(sync_placeholder)

        @functools.wraps(method)
        async def async_wrapper(*args, **kwargs):
            return await method(*args, **kwargs)

        # Carry forward any attributes the decorator added (e.g. csrf_exempt flag)
        for attr in dir(decorated):
            if attr.startswith("_"):
                continue
            with contextlib.suppress(AttributeError, TypeError):
                setattr(async_wrapper, attr, getattr(decorated, attr))

        return async_wrapper
    else:
        return decorator(method)
