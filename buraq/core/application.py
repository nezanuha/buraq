import importlib
from contextlib import asynccontextmanager

from fastapi import FastAPI

from buraq.conf import settings
from buraq.contrib.staticfiles import StaticFilesHandler
from buraq.exceptions import ImproperlyConfigured


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

        self._startup_hooks: list = []
        self._shutdown_hooks: list = []

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
        StaticFilesHandler(self).mount()
        self._register_exception_handlers()
        self._load_root_urlconf()
        self._register_welcome_page()

    def _register_welcome_page(self) -> None:
        """
        Answer a 404 at ``/`` with a "it works" page while DEBUG is on.

        A new project would otherwise reply ``{"detail":"Not Found"}`` at its own
        root, which reads as a broken install. The alternative -- scaffolding a
        placeholder view into config/urls.py -- puts a view in a URL
        configuration and leaves something to delete.

        Answering the 404 rather than claiming the route matters: urls can be
        registered after the application is built, via ``app.load_urls()``, and a
        route taken here would win over the project's own.
        """
        if not settings.DEBUG:
            return

        from starlette.exceptions import HTTPException as _StarletteHTTPException
        from starlette.requests import Request
        from starlette.responses import HTMLResponse, JSONResponse

        from buraq.core.welcome import welcome_html

        @self.exception_handler(404)
        async def _not_found(request: Request, exc: _StarletteHTTPException):
            if request.url.path == "/":
                return HTMLResponse(
                    welcome_html(
                        project=self.title, docs_url=self.docs_url or "/api/docs"
                    )
                )
            return JSONResponse(
                {"detail": getattr(exc, "detail", "Not Found")}, status_code=404
            )

    def _load_root_urlconf(self) -> None:
        """
        Register the URLs named by ROOT_URLCONF, if there are any.

        Without this a project had to reach back for the application to load its
        own URLs -- ``app.load_urls(urlpatterns)`` at the bottom of urls.py --
        which is why the application ended up being built there rather than in
        the entry point. Naming the module in settings lets urls.py hold nothing
        but urlpatterns.
        """
        module_path = getattr(settings, "ROOT_URLCONF", None)
        if not module_path:
            return

        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            raise ImproperlyConfigured(
                f"ROOT_URLCONF is {module_path!r}, which could not be imported: {exc}"
            ) from exc

        urlpatterns = getattr(module, "urlpatterns", None)
        if urlpatterns is None:
            raise ImproperlyConfigured(
                f"ROOT_URLCONF is {module_path!r}, which defines no urlpatterns."
            )
        self.load_urls(urlpatterns)

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

    #: Paths that no longer belong in MIDDLEWARE, and what replaced them. Each
    #: would otherwise fail quietly rather than loudly: Starlette's CORS class
    #: installs happily with no arguments and then applies no policy at all, so
    #: CORS_ORIGINS would be ignored and nothing would say so until a browser
    #: started refusing requests.
    _MIDDLEWARE_MOVED = {
        "fastapi.middleware.cors.CORSMiddleware": "buraq.middleware.cors.CORSMiddleware",
        "starlette.middleware.cors.CORSMiddleware": "buraq.middleware.cors.CORSMiddleware",
        "buraq.contrib.csrf.CsrfViewMiddleware": "buraq.middleware.csrf.CsrfViewMiddleware",
        "buraq.middleware.common.MessageMiddleware": (
            "buraq.contrib.messages.middleware.MessageMiddleware"
        ),
    }

    def _register_builtin_middleware(self) -> None:
        """
        Install the middleware named in the MIDDLEWARE setting.

        Starlette applies the last-added wrapper outermost, so the list is walked
        in reverse: that makes MIDDLEWARE[0] the first to see a request and the
        last to touch the response, which is the order the list reads in.
        """
        self._register_rate_limiter()

        for dotted in reversed(list(settings.MIDDLEWARE)):
            replacement = self._MIDDLEWARE_MOVED.get(dotted)
            if replacement:
                raise ImproperlyConfigured(
                    f"MIDDLEWARE names {dotted!r}, which Buraq no longer configures. "
                    f"Use {replacement!r} instead."
                )
            module_path, _, name = dotted.rpartition(".")
            try:
                middleware = getattr(importlib.import_module(module_path), name)
            except (ImportError, AttributeError) as exc:
                raise ImproperlyConfigured(
                    f"MIDDLEWARE names {dotted!r}, which could not be imported: {exc}"
                ) from exc
            # No arguments: Buraq's middleware reads its own settings, which is
            # the only way a dotted path in MIDDLEWARE can be configured at all.
            self.add_middleware(middleware)

    def _register_rate_limiter(self) -> None:
        """Wire slowapi's limiter when it is installed; it is an optional extra."""
        try:
            from slowapi import Limiter, _rate_limit_exceeded_handler
            from slowapi.errors import RateLimitExceeded
            from slowapi.util import get_remote_address
        except ImportError:
            return

        self.state.limiter = Limiter(
            key_func=get_remote_address, default_limits=[settings.RATE_LIMIT]
        )
        self.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    def on_startup(self, func):
        """
        Register a coroutine to run once the framework has finished starting up.

        Use this rather than replacing ``_on_startup``: that method is what loads
        INSTALLED_APPS, runs system checks and warms the template and translation
        caches, so overwriting it leaves the app running without any of them.

            @app.on_startup
            async def seed():
                ...
        """
        self._startup_hooks.append(func)
        return func

    def on_shutdown(self, func):
        """Register a coroutine to run before the framework tears itself down."""
        self._shutdown_hooks.append(func)
        return func

    async def _on_startup(self) -> None:
        # First: app configs connect signal receivers in ready(), and the checks
        # below inspect what those hooks register.
        from buraq.apps import setup as _setup_apps
        await _setup_apps()

        from buraq.checks.registry import registry
        registry.run_checks_or_raise()

        from buraq.core.templating import discover_templatetags
        discover_templatetags()

        if settings.USE_I18N:
            from buraq.utils.translation import warmup_catalogs
            warmup_catalogs()

        for hook in self._startup_hooks:
            await hook()

    async def _on_shutdown(self) -> None:
        # Application hooks first: they may still need the connection the engine
        # below is about to dispose of.
        for hook in reversed(self._shutdown_hooks):
            await hook()

        from buraq.core.db import _lazy
        if _lazy._engine is not None:
            await _lazy._engine.dispose()
