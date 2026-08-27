"""
``immutable`` is a promise that a URL will never serve different bytes.

Only a content-hashed name keeps that promise. It used to be sent for every
static response, including the default storage, which does not hash: an edited
stylesheet then failed to reach anyone who had already loaded the old one until
their cache entry expired a year later, and ``immutable`` tells a browser not to
revalidate even on reload.
"""

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from buraq.contrib.staticfiles.handlers import _CachedStaticFiles


@pytest.fixture
def css(tmp_path):
    path = tmp_path / "site.css"
    path.write_text("body{color:red}")
    return tmp_path


def _cache_control(directory, **kwargs):
    app = Starlette()
    app.mount("/static", _CachedStaticFiles(directory=str(directory), **kwargs), name="static")
    return TestClient(app).get("/static/site.css").headers["cache-control"]


def test_unhashed_names_are_not_immutable(css):
    """The default storage does not hash, so the same URL can serve new bytes."""
    value = _cache_control(css, immutable=False)
    assert "immutable" not in value
    assert "max-age=60" in value


def test_hashed_names_are_immutable_for_a_year(css):
    value = _cache_control(css, immutable=True)
    assert "immutable" in value
    assert "max-age=31536000" in value


def test_explicit_max_age_wins(css):
    assert "max-age=300" in _cache_control(css, max_age=300, immutable=False)
    assert "max-age=300" in _cache_control(css, max_age=300, immutable=True)


def test_immutable_tracks_the_configured_storage(monkeypatch, tmp_path):
    """The flag is derived from the storage, not passed in by hand at the mount."""
    from buraq.conf import settings
    from buraq.contrib.staticfiles.handlers import _storage_hashes_names
    from buraq.contrib.staticfiles.storage import reset_storage

    for dotted, expected in [
        ("buraq.contrib.staticfiles.storage.StaticFilesStorage", False),
        ("buraq.contrib.staticfiles.storage.ManifestStaticFilesStorage", True),
    ]:
        monkeypatch.setattr(settings, "STATICFILES_STORAGE", dotted, raising=False)
        monkeypatch.setattr(settings, "STATIC_ROOT", str(tmp_path), raising=False)
        reset_storage()
        assert _storage_hashes_names() is expected, dotted
    reset_storage()
