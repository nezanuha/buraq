"""Serving the admin's own assets.

Mounting the admin itself is done from urlpatterns -- ``path("/admin",
admin.site.urls)`` -- so where it lives is the project's choice rather than a
constant inside the router. This is the one part that cannot go through
urlpatterns, because a static mount is not a route.
"""

from pathlib import Path

_ADMIN_STATIC_DIR = Path(__file__).parent / "static"
_ADMIN_STATIC_URL = "/_buraq/static"


def _mount_admin_static(app) -> None:
    """Serve the admin's CSS, once, however many sites are mounted."""
    if not _ADMIN_STATIC_DIR.exists():
        return
    if any(getattr(route, "path", None) == _ADMIN_STATIC_URL for route in app.routes):
        return

    from fastapi.staticfiles import StaticFiles

    app.mount(
        _ADMIN_STATIC_URL,
        StaticFiles(directory=str(_ADMIN_STATIC_DIR)),
        name="_buraq_static",
    )


__all__: list[str] = []
