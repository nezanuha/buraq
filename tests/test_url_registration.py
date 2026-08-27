"""INSTALLED_APPS must not register URLs — only urlpatterns does.

Auto-registration mounted every app whose urls module declared no `prefix` at
the site root, in addition to wherever the project's own urlpatterns put it. A
project that followed the scaffold's instructions therefore bound each of its
routes twice, and the framework's own auth routes collided with the `include()`
the scaffold writes.
"""

import collections

import pytest

from buraq.urls import include, path


def _counts(app):
    seen = collections.Counter()
    for route in app.routes:
        for method in getattr(route, "methods", None) or []:
            if method not in ("HEAD", "OPTIONS"):
                seen[(getattr(route, "path", ""), method)] += 1
    return seen


@pytest.fixture
def app():
    from buraq.conf import settings

    settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    settings.DEBUG = True
    settings.SECRET_KEY = "test-secret-key-for-url-registration"
    settings.INSTALLED_APPS = ["buraq.contrib.auth"]

    import buraq.core.templating as _tmpl

    _tmpl._templates = None

    from buraq.core.application import Buraq

    return Buraq()


# The auth app's views, whatever prefix they might be mounted under.
_AUTH_SEGMENTS = ("login", "logout", "register")


def test_installed_apps_registers_no_urls(app):
    """buraq.contrib.auth is installed, but nothing mounted it — anywhere.

    Checking for the /auth prefix alone is not enough: auto-registration used
    the urls module's own `prefix`, so without one it mounted these at the site
    root instead, which an assertion about /auth would sail straight past.
    """
    leaked = sorted(
        p for p, _ in _counts(app) if any(seg in p for seg in _AUTH_SEGMENTS)
    )
    assert leaked == []


def test_include_mounts_each_route_exactly_once(app):
    app.load_urls([path("/auth", include("buraq.contrib.auth.urls"))])
    auth = {k: v for k, v in _counts(app).items() if k[0].startswith("/auth")}
    assert sorted(auth) == [
        ("/auth/login", "GET"),
        ("/auth/login", "POST"),
        ("/auth/logout", "GET"),
        ("/auth/logout", "POST"),
        ("/auth/register", "POST"),
    ]
    assert [k for k, v in auth.items() if v > 1] == []


def test_an_installed_app_does_not_leak_onto_the_root(app):
    """The failure that shadowed a project's own index view."""
    app.load_urls([path("/auth", include("buraq.contrib.auth.urls"))])
    counts = _counts(app)
    assert counts[("/", "GET")] == 0
    assert [p for p, _ in counts if p.startswith("/{")] == []
