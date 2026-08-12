"""
Content Security Policy middleware.

Adds ``Content-Security-Policy`` (and optionally ``Content-Security-Policy-Report-Only``)
headers to every response.

Configuration (``config/settings.py``)::

    MIDDLEWARE = [
        ...
        "buraq.middleware.csp.ContentSecurityPolicyMiddleware",
    ]

    # Required — define at least one of these:
    CONTENT_SECURITY_POLICY = {
        "default-src": ["'self'"],
        "script-src":  ["'self'"],
        "style-src":   ["'self'", "'unsafe-inline'"],
        "img-src":     ["'self'", "data:"],
    }

    # Optional — report-only header (does not block; only reports):
    CONTENT_SECURITY_POLICY_REPORT_ONLY = {
        "default-src": ["'self'"],
        "report-uri":  ["/csp-report/"],
    }

Both dicts accept directive names with either hyphens or underscores as separators.

Per-view overrides
------------------
Use decorators from ``buraq.views.decorators``::

    from buraq.views.decorators import csp_override, csp_report_only_override

    @csp_override(script_src=["'self'", "https://cdn.example.com"])
    async def my_view(request):
        ...

    @csp_report_only_override(default_src=["'self'"])
    async def another_view(request):
        ...

Nonces
------
Set ``CONTENT_SECURITY_POLICY_NONCE_DIRECTIVES`` to a list of directive names
that should receive an auto-generated per-request nonce::

    CONTENT_SECURITY_POLICY_NONCE_DIRECTIVES = ["script-src", "style-src"]

The nonce is available in templates as ``{{ csp_nonce }}``.
"""
from __future__ import annotations

import secrets
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_UNSET = object()  # sentinel: decorator was not applied to this view


def _build_header(policy: dict, nonce: str | None = None) -> str:
    """Render a CSP dict to a header value string."""
    parts: list[str] = []
    for directive, value in policy.items():
        name = directive.replace("_", "-")
        if value is True:
            parts.append(name)
        elif value is False or value is None:
            continue
        elif isinstance(value, (list, tuple)):
            sources = []
            for v in value:
                s = str(v)
                if "{nonce}" in s and nonce:
                    s = s.replace("{nonce}", nonce)
                sources.append(s)
            parts.append(f"{name} {' '.join(sources)}")
        else:
            rendered = str(value)
            if "{nonce}" in rendered and nonce:
                rendered = rendered.replace("{nonce}", nonce)
            parts.append(f"{name} {rendered}")
    return "; ".join(parts)


def _inject_nonce(policy: dict, nonce_directives: list[str], nonce: str) -> dict:
    """Return a copy of ``policy`` with ``'nonce-<nonce>'`` injected into each nonce directive."""
    result = dict(policy)
    nonce_token = f"'nonce-{nonce}'"
    for directive in nonce_directives:
        canonical = directive.replace("_", "-")
        for key in list(result.keys()):
            if key.replace("_", "-") == canonical:
                existing = result[key]
                if isinstance(existing, (list, tuple)):
                    result[key] = list(existing) + [nonce_token]
                else:
                    result[key] = [str(existing), nonce_token]
                break
        else:
            result[canonical] = [nonce_token]
    return result


class ContentSecurityPolicyMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that attaches CSP headers to every response.

    Reads policy from ``settings.CONTENT_SECURITY_POLICY`` and
    ``settings.CONTENT_SECURITY_POLICY_REPORT_ONLY``.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        from buraq.conf import settings

        csp_settings = getattr(settings, "CONTENT_SECURITY_POLICY", None)
        ro_settings = getattr(settings, "CONTENT_SECURITY_POLICY_REPORT_ONLY", None)
        nonce_directives: list[str] = getattr(
            settings, "CONTENT_SECURITY_POLICY_NONCE_DIRECTIVES", []
        )

        # Per-view override stored by decorator (_UNSET means no decorator applied)
        csp_override = getattr(request.state, "_csp_override", _UNSET)
        ro_override = getattr(request.state, "_csp_ro_override", _UNSET)

        effective_csp = csp_override if csp_override is not _UNSET else csp_settings
        effective_ro = ro_override if ro_override is not _UNSET else ro_settings

        nonce: str | None = None
        if nonce_directives and (effective_csp or effective_ro):
            nonce = secrets.token_urlsafe(16)
            request.state.csp_nonce = nonce
        else:
            request.state.csp_nonce = None

        response = await call_next(request)

        if effective_csp:
            policy = (
                _inject_nonce(effective_csp, nonce_directives, nonce) if nonce else effective_csp
            )
            response.headers["Content-Security-Policy"] = _build_header(policy, nonce)

        if effective_ro:
            policy = _inject_nonce(effective_ro, nonce_directives, nonce) if nonce else effective_ro
            response.headers["Content-Security-Policy-Report-Only"] = _build_header(policy, nonce)

        return response
