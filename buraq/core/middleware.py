from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from buraq.conf import settings


def register_middleware(app: FastAPI) -> None:
    # Rate limiting — optional, only if slowapi is installed
    try:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded
        from slowapi.util import get_remote_address
        limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT])
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    except ImportError:
        pass

    app.add_middleware(GZipMiddleware, minimum_size=1000)

    cors_origins = settings.CORS_ORIGINS  # empty list = CORS disabled (no wildcard fallback)
    # Browsers reject allow_credentials=True with wildcard origins.
    # Disable credentials automatically when origins are not explicitly scoped.
    cors_credentials = bool(cors_origins) and settings.CORS_ALLOW_CREDENTIALS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=cors_credentials,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )

    # Use Buraq signed-cookie session middleware (sets request.session).
    from buraq.contrib.sessions.middleware import SessionMiddleware
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY,
        https_only=not settings.DEBUG,
    )

    if settings.ALLOWED_HOSTS != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)


async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    if settings.SECURE_CONTENT_TYPE_NOSNIFF:
        response.headers["X-Content-Type-Options"] = "nosniff"
    if settings.X_FRAME_OPTIONS:
        response.headers["X-Frame-Options"] = settings.X_FRAME_OPTIONS
    response.headers["X-XSS-Protection"] = "1; mode=block"
    if settings.SECURE_REFERRER_POLICY:
        response.headers["Referrer-Policy"] = settings.SECURE_REFERRER_POLICY
    if settings.SECURE_CROSS_ORIGIN_OPENER_POLICY:
        response.headers["Cross-Origin-Opener-Policy"] = settings.SECURE_CROSS_ORIGIN_OPENER_POLICY
    if settings.SECURE_HSTS_SECONDS > 0:
        hsts = f"max-age={settings.SECURE_HSTS_SECONDS}"
        if settings.SECURE_HSTS_INCLUDE_SUBDOMAINS:
            hsts += "; includeSubDomains"
        if settings.SECURE_HSTS_PRELOAD:
            hsts += "; preload"
        response.headers["Strict-Transport-Security"] = hsts
    return response
