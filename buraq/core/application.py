import importlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from buraq.conf import settings
from buraq.contrib.staticfiles import StaticFilesHandler


class Buraq(FastAPI):
    """
    The main Buraq application class.

    Usage:
        from buraq import Buraq
        from buraq.urls import path, include

        app = Buraq(settings_module="config.settings")

        urlpatterns = [
            path('/auth',  include('buraq.contrib.auth.urls')),
            path('/posts', include('posts.urls')),
        ]
        app.load_urls(urlpatterns)
    """

    def __init__(self, settings_module: str | None = None, **kwargs):
        if settings_module:
            self._load_settings(settings_module)

        @asynccontextmanager
        async def lifespan(app: "Buraq"):
            await self._on_startup()
            yield
            await self._on_shutdown()

        super().__init__(
            title=kwargs.pop("title", "Buraq App"),
            version=kwargs.pop("version", "1.0.0"),
            docs_url="/api/docs" if settings.DEBUG else None,
            redoc_url="/api/redoc" if settings.DEBUG else None,
            lifespan=lifespan,
            **kwargs,
        )

        self._register_builtin_middleware()
        self.middleware("http")(self._security_headers_middleware)
        StaticFilesHandler(self).mount()
        self._register_apps()
        self._register_exception_handlers()

    def load_urls(self, urlpatterns: list) -> None:
        """
        Register urlpatterns with the application.

        app.load_urls([
            path('/auth',  include('buraq.contrib.auth.urls')),
            path('/posts', include('posts.urls')),
        ])
        """
        from buraq.urls import register_urlpatterns
        register_urlpatterns(self, urlpatterns)

    def _load_settings(self, module_path: str) -> None:
        module = importlib.import_module(module_path)
        user_settings = {
            k: v for k, v in vars(module).items()
            if k.isupper() and not k.startswith("_")
        }
        for key, value in user_settings.items():
            object.__setattr__(settings, key, value)

    def _register_apps(self) -> None:
        """Auto-register URLs from INSTALLED_APPS — supports both router and urlpatterns styles."""
        from buraq.urls import register_urlpatterns
        for app_name in settings.INSTALLED_APPS:
            try:
                urls_module = importlib.import_module(f"{app_name}.urls")
                if hasattr(urls_module, "router"):
                    self.include_router(urls_module.router)
                elif hasattr(urls_module, "urlpatterns"):
                    # Optional `prefix` on the urls module
                    app_prefix = getattr(urls_module, "prefix", "")
                    register_urlpatterns(self, urls_module.urlpatterns, prefix=app_prefix)
            except ModuleNotFoundError:
                pass

    def _register_exception_handlers(self) -> None:
        from starlette.requests import Request
        from starlette.responses import HTMLResponse

        from buraq.http import Http404

        @self.exception_handler(Http404)
        async def _http404_handler(request: Request, exc: Http404) -> HTMLResponse:
            detail = str(exc) if str(exc) else "Not Found"
            return HTMLResponse(content=detail, status_code=404)

        @self.exception_handler(Exception)
        async def _debug_exception_handler(request: Request, exc: Exception) -> HTMLResponse:
            from starlette.exceptions import HTTPException as _HTTPExc
            if isinstance(exc, _HTTPExc):
                return HTMLResponse(content=exc.detail or "Error", status_code=exc.status_code)
            if not settings.DEBUG:
                return HTMLResponse(content="Internal Server Error", status_code=500)
            import traceback as _tb
            _tb.print_exc()
            from buraq.core.debug import render_debug_page
            return HTMLResponse(content=render_debug_page(request, exc), status_code=500)

    def _register_builtin_middleware(self) -> None:
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.middleware.gzip import GZipMiddleware
        from fastapi.middleware.trustedhost import TrustedHostMiddleware

        try:
            from slowapi import Limiter, _rate_limit_exceeded_handler
            from slowapi.errors import RateLimitExceeded
            from slowapi.util import get_remote_address
            limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT])
            self.state.limiter = limiter
            self.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        except ImportError:
            pass

        self.add_middleware(GZipMiddleware, minimum_size=1000)

        cors_origins = settings.CORS_ORIGINS
        cors_credentials = bool(cors_origins) and settings.CORS_ALLOW_CREDENTIALS
        self.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=cors_credentials,
            allow_methods=settings.CORS_ALLOW_METHODS,
            allow_headers=settings.CORS_ALLOW_HEADERS,
        )

        from buraq.contrib.sessions.middleware import SessionMiddleware
        self.add_middleware(
            SessionMiddleware,
            secret_key=settings.SECRET_KEY,
            https_only=not settings.DEBUG,
        )

        if settings.ALLOWED_HOSTS != ["*"]:
            self.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

    @staticmethod
    async def _security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        if settings.SECURE_CONTENT_TYPE_NOSNIFF:
            response.headers["X-Content-Type-Options"] = "nosniff"
        if settings.X_FRAME_OPTIONS:
            response.headers["X-Frame-Options"] = settings.X_FRAME_OPTIONS
        response.headers["X-XSS-Protection"] = "1; mode=block"
        if settings.SECURE_REFERRER_POLICY:
            response.headers["Referrer-Policy"] = settings.SECURE_REFERRER_POLICY
        if settings.SECURE_CROSS_ORIGIN_OPENER_POLICY:
            response.headers["Cross-Origin-Opener-Policy"] = (
                settings.SECURE_CROSS_ORIGIN_OPENER_POLICY
            )
        if settings.SECURE_HSTS_SECONDS > 0:
            hsts = f"max-age={settings.SECURE_HSTS_SECONDS}"
            if settings.SECURE_HSTS_INCLUDE_SUBDOMAINS:
                hsts += "; includeSubDomains"
            if settings.SECURE_HSTS_PRELOAD:
                hsts += "; preload"
            response.headers["Strict-Transport-Security"] = hsts
        return response

    async def _on_startup(self) -> None:
        from buraq.checks.registry import registry
        registry.run_checks_or_raise()

        from buraq.core.templating import discover_templatetags
        discover_templatetags()

        if settings.USE_I18N:
            from buraq.utils.translation import warmup_catalogs
            warmup_catalogs()

    async def _on_shutdown(self) -> None:
        from buraq.core.db import _lazy
        if _lazy._engine is not None:
            await _lazy._engine.dispose()
