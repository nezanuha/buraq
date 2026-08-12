"""
Per-view CSP override decorators.

These decorators let individual views override the global CSP policy set in
``settings.CONTENT_SECURITY_POLICY`` / ``settings.CONTENT_SECURITY_POLICY_REPORT_ONLY``.

Usage::

    from buraq.views.decorators import csp_override, csp_report_only_override

    @csp_override(
        default_src=["'self'"],
        script_src=["'self'", "https://cdn.example.com"],
    )
    async def my_view(request):
        ...

    @csp_report_only_override(default_src=["'self'"], report_uri=["/csp-report/"])
    async def another_view(request):
        ...

Pass ``None`` to disable the policy for a specific view::

    @csp_override(None)
    async def embed_view(request):
        ...
"""
from __future__ import annotations

import functools
from typing import Callable


def csp_override(policy: dict | None = None, **directives) -> Callable:
    """
    Override the enforced ``Content-Security-Policy`` for a single view.

    Pass either a single dict or keyword arguments (directive names with
    underscores as separators).  Pass ``None`` to suppress the CSP header.
    """
    if policy is None and directives:
        policy = directives

    def decorator(view_func: Callable) -> Callable:
        _policy = policy
        @functools.wraps(view_func)
        async def wrapper(request, *args, **kwargs):
            request.state._csp_override = _policy
            return await view_func(request, *args, **kwargs)
        return wrapper

    return decorator


def csp_report_only_override(policy: dict | None = None, **directives) -> Callable:
    """
    Override the ``Content-Security-Policy-Report-Only`` header for a single view.

    Does not affect the enforced ``Content-Security-Policy`` header.
    """
    if policy is None and directives:
        policy = directives

    def decorator(view_func: Callable) -> Callable:
        _policy = policy
        @functools.wraps(view_func)
        async def wrapper(request, *args, **kwargs):
            request.state._csp_ro_override = _policy
            return await view_func(request, *args, **kwargs)
        return wrapper

    return decorator
