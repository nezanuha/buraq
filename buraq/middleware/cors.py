"""Cross-Origin Resource Sharing, configured from settings.

Starlette's own CORS middleware takes its configuration as constructor
arguments, which a dotted path in MIDDLEWARE has no way to supply. This reads
the ``CORS_*`` settings instead, so it can be listed like every other entry and
the settings named in the documentation are the ones that apply.

Arguments still win where one is given, for a project that wants a second CORS
policy on a mounted sub-application.
"""

from __future__ import annotations

from typing import Any

from starlette.middleware.cors import CORSMiddleware as _StarletteCORSMiddleware

__all__ = ["CORSMiddleware"]


class CORSMiddleware(_StarletteCORSMiddleware):
    """CORS headers, with defaults taken from ``CORS_*`` settings."""

    def __init__(
        self,
        app: Any,
        allow_origins: list[str] | None = None,
        allow_methods: list[str] | None = None,
        allow_headers: list[str] | None = None,
        allow_credentials: bool | None = None,
        **kwargs: Any,
    ) -> None:
        from buraq.conf import settings

        origins = (
            allow_origins
            if allow_origins is not None
            else list(getattr(settings, "CORS_ORIGINS", None) or [])
        )
        if allow_credentials is None:
            # A browser rejects a credentialed request whose response says
            # `Access-Control-Allow-Origin: *`, so credentials only mean
            # anything once specific origins are named.
            allow_credentials = bool(origins) and getattr(
                settings, "CORS_ALLOW_CREDENTIALS", True
            )

        super().__init__(
            app,
            allow_origins=origins,
            allow_methods=(
                allow_methods
                if allow_methods is not None
                else list(getattr(settings, "CORS_ALLOW_METHODS", None) or ["*"])
            ),
            allow_headers=(
                allow_headers
                if allow_headers is not None
                else list(getattr(settings, "CORS_ALLOW_HEADERS", None) or ["*"])
            ),
            allow_credentials=allow_credentials,
            **kwargs,
        )
