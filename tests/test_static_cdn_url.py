"""
A CDN is configured by pointing STATIC_URL at it, not by pointing the server at it.

Setting it used to crash at startup: the mount was attempted with the CDN host
as its route path, and Starlette rejected it -- ``Routed paths must start with
'/'`` -- an AssertionError naming neither STATIC_URL nor the CDN.

The host is now dropped and the path kept, because a pull zone fetches from this
origin on a cache miss: templates point at the CDN, and the files still have to
be reachable here. Uploading to the CDN instead is SERVE_STATIC = False.
"""

import pytest
from fastapi import FastAPI

from buraq.conf import settings
from buraq.contrib.staticfiles.handlers import StaticFilesHandler, _mount_path
from buraq.contrib.staticfiles.storage import _is_absolute_url


@pytest.mark.parametrize(
    "url,absolute",
    [
        ("/static/", False),
        ("static/", False),
        ("", False),
        ("https://cdn.example.com/static/", True),
        ("http://cdn.example.com/static/", True),
        ("//cdn.example.com/static/", True),
    ],
)
def test_absolute_url_detection(url, absolute):
    assert _is_absolute_url(url) is absolute


@pytest.mark.parametrize(
    "url",
    ["static/", "static", "assets/v2/"],
)
def test_missing_leading_slash_is_added(url):
    """``STATIC_URL = "static/"`` reads like ``/static/`` and now behaves like it.

    Left alone it produced a relative href -- resolving differently on every page
    -- and Starlette refused it as a mount path with an error naming nothing.
    """
    mounted = _mount_path(url)
    assert mounted.startswith("/"), "would raise AssertionError at startup"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("/static/", "/static"),
        ("/static", "/static"),
        ("static/", "/static"),
        ("static", "/static"),
        ("https://cdn.example.com/static/", "/static"),
        ("//cdn.example.com/static/", "/static"),
        ("https://cdn.b-cdn.net/assets/v2/", "/assets/v2"),
        # No path left to mount at -- "/" would swallow every route.
        ("https://cdn.example.com/", None),
        ("https://cdn.example.com", None),
    ],
)
def test_mount_path(url, expected):
    assert _mount_path(url) == expected


def test_cdn_static_url_mounts_at_the_path_not_the_host(monkeypatch, tmp_path):
    """A pull zone fetches from this origin, so the files stay reachable here."""
    (tmp_path / "site.css").write_text("body{}")
    monkeypatch.setattr(settings, "STATIC_URL", "https://cdn.example.com/static/", raising=False)
    monkeypatch.setattr(settings, "STATIC_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "SERVE_STATIC", True, raising=False)
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)

    app = FastAPI()
    StaticFilesHandler(app).mount()   # used to raise AssertionError

    paths = [getattr(r, "path", "") for r in app.routes]
    assert not any("cdn.example.com" in p for p in paths)
    assert "/static" in paths, "a pull zone would get a 404 from its own origin"


def test_upload_to_cdn_is_serve_static_false(monkeypatch, tmp_path):
    """Uploading to the CDN means nothing is served here -- that is the switch."""
    (tmp_path / "site.css").write_text("body{}")
    monkeypatch.setattr(settings, "STATIC_URL", "https://cdn.example.com/static/", raising=False)
    monkeypatch.setattr(settings, "STATIC_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "SERVE_STATIC", False, raising=False)
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)

    app = FastAPI()
    StaticFilesHandler(app).mount()

    assert not any(getattr(r, "path", "") == "/static" for r in app.routes)


def test_cdn_media_url_mounts_at_the_path(monkeypatch, tmp_path):
    (tmp_path / "photo.jpg").write_bytes(b"x")
    monkeypatch.setattr(settings, "STATIC_URL", "/static/", raising=False)
    monkeypatch.setattr(settings, "MEDIA_URL", "https://cdn.example.com/media/", raising=False)
    monkeypatch.setattr(settings, "MEDIA_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "STATIC_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "SERVE_STATIC", True, raising=False)
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)

    app = FastAPI()
    StaticFilesHandler(app).mount()

    paths = [getattr(r, "path", "") for r in app.routes]
    assert not any("cdn.example.com" in p for p in paths)
    assert "/media" in paths


def test_local_static_url_still_mounts(monkeypatch, tmp_path):
    """The fix must not stop the ordinary case working."""
    (tmp_path / "site.css").write_text("body{}")
    monkeypatch.setattr(settings, "STATIC_URL", "/static/", raising=False)
    monkeypatch.setattr(settings, "STATIC_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(settings, "SERVE_STATIC", True, raising=False)
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)

    app = FastAPI()
    StaticFilesHandler(app).mount()

    assert any(getattr(r, "path", "") == "/static" for r in app.routes)
