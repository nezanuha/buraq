import importlib
from contextlib import asynccontextmanager

from fastapi import FastAPI

from buraq.conf import settings
from buraq.core.middleware import register_middleware, security_headers_middleware
from buraq.core.templating import register_static


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

        register_middleware(self)
        self.middleware("http")(security_headers_middleware)
        register_static(self)
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
            if hasattr(settings, key):
                setattr(settings, key, value)

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

    async def _on_startup(self) -> None:
        from buraq.core.templating import discover_templatetags
        discover_templatetags()

        if settings.USE_I18N:
            from buraq.utils.translation import warmup_catalogs
            warmup_catalogs()

    async def _on_shutdown(self) -> None:
        from buraq.core.db import engine
        await engine.dispose()
