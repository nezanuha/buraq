"""
Development serves from every directory collectstatic collects from.

The dev mount only looked at STATIC_DIR, while the finders behind collectstatic
read STATICFILES_DIRS and each installed app's static/ as well. A project using
STATICFILES_DIRS -- which is the setting the framework itself prefers -- got its
files collected correctly in production and a 404 while developing, which reads
as a missing file rather than a missing mount.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from buraq.conf import settings
from buraq.contrib.staticfiles.handlers import StaticFilesHandler


@pytest.fixture
def dev(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", True, raising=False)
    monkeypatch.setattr(settings, "SERVE_STATIC", True, raising=False)
    monkeypatch.setattr(settings, "STATIC_URL", "/static/", raising=False)
    monkeypatch.setattr(settings, "INSTALLED_APPS", [], raising=False)

    def serve(**overrides):
        for name, value in overrides.items():
            monkeypatch.setattr(settings, name, value, raising=False)
        app = FastAPI()
        StaticFilesHandler(app).mount()
        return TestClient(app)

    return serve


def test_staticfiles_dirs_is_served(dev, tmp_path):
    theme = tmp_path / "theme"
    theme.mkdir()
    (theme / "brand.css").write_text("body{}")

    client = dev(STATIC_DIR=None, STATICFILES_DIRS=[str(theme)])
    assert client.get("/static/brand.css").status_code == 200


def test_static_dir_is_still_served(dev, tmp_path):
    own = tmp_path / "static"
    own.mkdir()
    (own / "site.css").write_text("body{}")

    client = dev(STATIC_DIR=str(own), STATICFILES_DIRS=[])
    assert client.get("/static/site.css").status_code == 200


def test_several_directories_are_searched(dev, tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    for d in (first, second):
        d.mkdir()
    (first / "one.css").write_text("a{}")
    (second / "two.css").write_text("b{}")

    client = dev(STATIC_DIR=None, STATICFILES_DIRS=[str(first), str(second)])
    assert client.get("/static/one.css").status_code == 200
    assert client.get("/static/two.css").status_code == 200


def test_earlier_directories_win(dev, tmp_path):
    """Same order as the finders, so development matches what collectstatic keeps."""
    first, second = tmp_path / "a", tmp_path / "b"
    for d in (first, second):
        d.mkdir()
    (first / "app.css").write_text("/* first */")
    (second / "app.css").write_text("/* second */")

    client = dev(STATIC_DIR=None, STATICFILES_DIRS=[str(first), str(second)])
    assert client.get("/static/app.css").text == "/* first */"


def test_nothing_is_mounted_when_no_directory_exists(dev, tmp_path):
    client = dev(STATIC_DIR=str(tmp_path / "absent"), STATICFILES_DIRS=[])
    assert client.get("/static/anything.css").status_code == 404
