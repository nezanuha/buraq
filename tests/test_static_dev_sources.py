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


def test_an_installed_apps_static_is_served(dev, tmp_path, monkeypatch):
    """The URL is /static/<app>/<file>, so the mount root is the app's static/.

    Taking the directory a file sits in instead gives .../static/shop, under
    which /static/shop/cart.js cannot resolve -- collected fine, 404 in
    development.
    """
    import sys

    app = tmp_path / "shop"
    (app / "static" / "shop").mkdir(parents=True)
    (app / "__init__.py").write_text("")
    (app / "static" / "shop" / "cart.js").write_text("// cart")
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("shop", None)

    client = dev(STATIC_DIR=None, STATICFILES_DIRS=[], INSTALLED_APPS=["shop"])
    response = client.get("/static/shop/cart.js")
    assert response.status_code == 200
    assert response.text == "// cart"


def test_development_and_collectstatic_agree(dev, tmp_path, monkeypatch):
    """Whatever collectstatic would collect must resolve while developing."""
    import sys

    from buraq.contrib.staticfiles import collect_static
    from buraq.contrib.staticfiles.storage import reset_storage

    theme = tmp_path / "theme"
    theme.mkdir()
    (theme / "brand.css").write_text("body{}")
    app = tmp_path / "blog"
    (app / "static" / "blog").mkdir(parents=True)
    (app / "__init__.py").write_text("")
    (app / "static" / "blog" / "post.css").write_text("p{}")
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("blog", None)

    client = dev(STATIC_DIR=None, STATICFILES_DIRS=[str(theme)], INSTALLED_APPS=["blog"])
    monkeypatch.setattr(settings, "STATIC_ROOT", str(tmp_path / "out"), raising=False)
    reset_storage()
    collect_static()
    reset_storage()

    for rel in ("brand.css", "blog/post.css"):
        assert (tmp_path / "out" / rel).exists(), f"collectstatic missed {rel}"
        assert client.get(f"/static/{rel}").status_code == 200, f"development missed {rel}"


def test_no_implicit_static_directory(dev, tmp_path, monkeypatch):
    """./static is not served unless something actually configures it.

    The handler used to fall back to ./static when STATIC_DIR was unset, while
    the finders did not -- so a file there was served while developing and
    absent after collectstatic, which is the worse way round for the two to
    disagree.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "static").mkdir()
    (tmp_path / "static" / "local.css").write_text("a{}")
    theme = tmp_path / "theme"
    theme.mkdir()
    (theme / "brand.css").write_text("b{}")

    client = dev(STATIC_DIR=None, STATICFILES_DIRS=[str(theme)])
    assert client.get("/static/brand.css").status_code == 200
    assert client.get("/static/local.css").status_code == 404


def test_development_serves_exactly_what_the_finders_search(dev, tmp_path, monkeypatch):
    """One list, so the two cannot drift apart again."""
    import sys


    theme = tmp_path / "theme"
    theme.mkdir()
    (theme / "brand.css").write_text("b{}")
    app = tmp_path / "news"
    (app / "static" / "news").mkdir(parents=True)
    (app / "__init__.py").write_text("")
    (app / "static" / "news" / "feed.css").write_text("n{}")
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("news", None)

    client = dev(STATIC_DIR=None, STATICFILES_DIRS=[str(theme)], INSTALLED_APPS=["news"])
    assert client.get("/static/brand.css").status_code == 200
    assert client.get("/static/news/feed.css").status_code == 200


def test_a_custom_finder_is_served(dev, tmp_path, monkeypatch):
    """A finder with files but no directories -- the shape the docs show.

    Mounting directories could not serve one at all: there is nothing to mount.
    Development resolves through the finders instead, so anything collectstatic
    can collect is reachable while building.
    """
    import sys

    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "lib.js").write_text("// lib")
    (tmp_path / "myfinders.py").write_text(
        "from pathlib import Path\n\n"
        "class NodeModulesFinder:\n"
        "    def find(self, path):\n"
        "        full = Path('node_modules') / path\n"
        "        return str(full) if full.is_file() else None\n\n"
        "    def list(self):\n"
        "        for f in Path('node_modules').rglob('*'):\n"
        "            if f.is_file():\n"
        "                yield f.relative_to('node_modules').as_posix(), str(f)\n"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    sys.modules.pop("myfinders", None)

    client = dev(
        STATIC_DIR=None,
        STATICFILES_DIRS=[],
        INSTALLED_APPS=[],
        STATICFILES_FINDERS=["myfinders.NodeModulesFinder"],
    )
    assert client.get("/static/pkg/lib.js").status_code == 200


def test_a_path_cannot_escape_upwards(dev, tmp_path, monkeypatch):
    """Resolving through the finders must not become a way out of them."""
    secret = tmp_path / "secret.txt"
    secret.write_text("nope")
    served = tmp_path / "static"
    served.mkdir()
    (served / "ok.css").write_text("a{}")

    client = dev(STATIC_DIR=None, STATICFILES_DIRS=[str(served)])
    assert client.get("/static/ok.css").status_code == 200
    for attempt in ("/static/../secret.txt", "/static/%2e%2e/secret.txt"):
        assert client.get(attempt).status_code in (400, 404), attempt
