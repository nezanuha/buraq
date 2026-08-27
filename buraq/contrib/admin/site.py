from __future__ import annotations

import contextlib
import importlib
from typing import TYPE_CHECKING

from buraq.conf import settings

if TYPE_CHECKING:
    from buraq.contrib.admin.options import ModelAdmin


class AdminSite:
    #: Where the admin was mounted, set by register_urlpatterns. Every URL the
    #: admin builds hangs off this, so moving it in urlpatterns moves its
    #: redirects with it.
    prefix: str = "/admin"

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

    @property
    def urls(self) -> _AdminURLs:
        """Mount with ``path("/admin", admin.site.urls)``."""
        return _AdminURLs(self)

    def autodiscover(self):
        for app_name in getattr(settings, "INSTALLED_APPS", []):
            with contextlib.suppress(ModuleNotFoundError):
                importlib.import_module(f"{app_name}.admin")


class _AdminURLs:
    """
    What ``admin.site.urls`` hands to ``path()``.

    A marker rather than a router: mounting the admin also means discovering
    each app's admin.py and serving the admin's own assets, and those need the
    application, which only ``register_urlpatterns`` has. Carrying the site
    through lets the prefix be chosen at the call site -- ``path("/admin", ...)``
    or anywhere else -- instead of being fixed inside the router.
    """

    def __init__(self, admin_site: AdminSite) -> None:
        self.site = admin_site


site = AdminSite()
