"""
Static names are URL paths, so they must use ``/`` on every platform.

They were built with ``str(Path(...))``, which yields a backslash separator on
Windows. The damage was silent rather than loud: the manifest was written with
``css\site.css`` as its key, every ``{{ static('css/site.css') }}`` lookup
missed it, and the unhashed name was returned instead -- so cache-busting did
nothing at all, with no error to notice. Had the lookup hit, the value carried a
backslash into the rendered href, which a CDN answers with a 404.
"""

import json

import pytest

from buraq.conf import settings
from buraq.contrib.staticfiles import collect_static
from buraq.contrib.staticfiles.storage import (
    ManifestStaticFilesStorage,
    reset_storage,
)


@pytest.fixture
def collected(tmp_path, monkeypatch):
    """collectstatic over a nested source tree, with hashing on."""
    source = tmp_path / "src"
    (source / "css" / "vendor").mkdir(parents=True)
    # Bytes, not text: write_text turns "\n" into "\r\n" on Windows, so the file
    # differed by platform and so did its content hash. The assertions below
    # name a hash, so they passed on the machine it was taken from and failed on
    # every other one -- which was four of the six CI jobs.
    (source / "css" / "vendor" / "reset.css").write_bytes(
        b"*{box-sizing:border-box}\n" * 40
    )
    dest = tmp_path / "out"

    monkeypatch.setattr(settings, "STATIC_DIR", str(source), raising=False)
    monkeypatch.setattr(settings, "STATIC_ROOT", str(dest), raising=False)
    monkeypatch.setattr(settings, "STATIC_URL", "https://my-zone.b-cdn.net/static/", raising=False)
    monkeypatch.setattr(
        settings,
        "STATICFILES_STORAGE",
        "buraq.contrib.staticfiles.storage.ManifestStaticFilesStorage",
        raising=False,
    )
    monkeypatch.setattr(settings, "STATICFILES_DIRS", [], raising=False)
    reset_storage()
    yield collect_static(), dest
    reset_storage()


def test_manifest_uses_forward_slashes(collected):
    _, dest = collected
    paths = json.loads((dest / "staticfiles.json").read_text())["paths"]
    assert paths == {"css/vendor/reset.css": "css/vendor/reset.b204b0c5.css"}
    for key, value in paths.items():
        assert "\\" not in key and "\\" not in value


def test_hashed_url_is_found_and_is_a_valid_url(collected):
    from buraq.contrib.staticfiles.storage import get_storage

    url = get_storage().url("css/vendor/reset.css")
    assert url == "https://my-zone.b-cdn.net/static/css/vendor/reset.b204b0c5.css"
    assert "\\" not in url, "a backslash here is a 404 on a CDN"
    assert url.rsplit("/", 1)[-1] != "reset.css", "fell back to the unhashed name"


@pytest.mark.parametrize(
    "name,expected",
    [
        ("site.css", "site.abc123.css"),
        ("css/site.css", "css/site.abc123.css"),
        ("css/vendor/reset.css", "css/vendor/reset.abc123.css"),
        # A caller that hands over a Windows-style name still gets a URL back.
        ("css\site.css", "css/site.abc123.css"),
    ],
)
def test_hashed_name_is_posix(name, expected):
    assert ManifestStaticFilesStorage._hashed_name(name, "abc123") == expected
