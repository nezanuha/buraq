from pathlib import Path

from buraq.contrib.admin.site import site

_ADMIN_STATIC_DIR = Path(__file__).parent / "static"
_ADMIN_STATIC_URL = "/_buraq/static"


class BuraqAdmin:
    """Mount the Buraq built-in admin panel on the given application."""

    def __init__(self, app, admin_site=None):
        if admin_site is None:
            admin_site = site
        self.admin_site = admin_site
        admin_site.autodiscover()
        from buraq.contrib.admin.views import get_admin_router
        app.include_router(get_admin_router(admin_site))
        self._mount_static(app)

    @staticmethod
    def _mount_static(app) -> None:
        if not _ADMIN_STATIC_DIR.exists():
            return
        from fastapi.staticfiles import StaticFiles
        app.mount(
            _ADMIN_STATIC_URL,
            StaticFiles(directory=str(_ADMIN_STATIC_DIR)),
            name="_buraq_static",
        )
