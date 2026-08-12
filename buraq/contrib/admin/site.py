from __future__ import annotations

import contextlib
import importlib
from typing import TYPE_CHECKING

from buraq.conf import settings

if TYPE_CHECKING:
    from buraq.contrib.admin.options import ModelAdmin


class AdminSite:
    def __init__(self):
        self._registry: dict[type, ModelAdmin] = {}
        self.site_header = "Buraq Administration"
        self.site_title = "Buraq Admin"
        self.index_title = "Dashboard"

    def register(self, model, admin_class=None, **options):
        from buraq.contrib.admin.options import ModelAdmin as _ModelAdmin
        if admin_class is None:
            admin_class = _ModelAdmin
        if options:
            admin_class = type(f"{model.__name__}Admin", (admin_class,), options)
        self._registry[model] = admin_class(model, self)

    def unregister(self, model):
        self._registry.pop(model, None)

    def is_registered(self, model) -> bool:
        return model in self._registry

    def autodiscover(self):
        for app_name in getattr(settings, "INSTALLED_APPS", []):
            with contextlib.suppress(ModuleNotFoundError):
                importlib.import_module(f"{app_name}.admin")


site = AdminSite()
