"""The page a new project shows at / until it routes it.

Without one, a freshly scaffolded project answered {"detail":"Not Found"} at its
own root, which reads as a broken install rather than an empty one.
"""

import pytest


@pytest.fixture
def make_app():
    def _make(*, debug: bool, urlpatterns=None):
        from buraq.conf import settings

        settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
        settings.SECRET_KEY = "x" * 32
        settings.INSTALLED_APPS = []
        settings.ROOT_URLCONF = None
        settings.DEBUG = debug

        from buraq.core.application import Buraq

        app = Buraq()
        if urlpatterns:
            app.load_urls(urlpatterns)
        return app

    return _make


def test_a_project_with_no_root_route_is_greeted(make_app):
    from fastapi.testclient import TestClient

    with TestClient(make_app(debug=True)) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "It works." in response.text


def test_the_project_own_route_wins(make_app):
    """The page is a stand-in, not a squatter."""
    from fastapi.testclient import TestClient

    from buraq.urls import path

    async def home(request):
        return {"mine": True}

    app = make_app(debug=True, urlpatterns=[path("/", home)])
    with TestClient(app) as client:
        assert client.get("/").json() == {"mine": True}


def test_never_shown_in_production(make_app):
    """It names the framework and links the admin; neither belongs on a live site."""
    from fastapi.testclient import TestClient

    with TestClient(make_app(debug=False)) as client:
        response = client.get("/")

    assert response.status_code == 404
    assert "It works." not in response.text
