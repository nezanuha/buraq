import importlib

from fastapi import FastAPI

from buraq.conf import settings

try:
    from sqladmin import Admin
    from sqladmin import ModelView as _ModelView
    _sqladmin_available = True
except ImportError:
    _sqladmin_available = False
    _ModelView = object


class ModelAdmin(_ModelView):
    """Base class for registering a model with the admin interface."""
    pass


class BuraqAdmin:
    """
    Auto-discovers admin.py in each INSTALLED_APP and registers views.
    Requires: uv add sqladmin

    Usage in config/urls.py:
        from buraq.contrib.admin import BuraqAdmin
        admin = BuraqAdmin(app)
    """

    def __init__(self, app: FastAPI):
        if not _sqladmin_available:
            raise ImportError(
                "sqladmin is required for BuraqAdmin. Install it with: uv add sqladmin"
            )
        from buraq.core.db import engine
        self._admin = Admin(
            app,
            engine,
            title="Buraq Admin",
            base_url="/admin",
            templates_dir=None,
        )
        self._autodiscover()

    def _autodiscover(self) -> None:
        for app_name in settings.INSTALLED_APPS:
            try:
                module = importlib.import_module(f"{app_name}.admin")
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, ModelAdmin)
                        and attr is not ModelAdmin
                    ):
                        self._admin.add_view(attr)
            except ModuleNotFoundError:
                pass

    def add_view(self, view: type) -> None:
        self._admin.add_view(view)
