"""Pre-compressed static files.

GZipMiddleware compresses each response as it is sent -- about 2.8 ms of CPU for
a 97 KB stylesheet, repeated for bytes that never change. collectstatic writes a
.gz once and the handler serves it directly.
"""

import gzip

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def serve(tmp_path, monkeypatch):
    def _serve(name: str, body: bytes, *, precompress: bool):
        from buraq.conf import settings
        from buraq.core.application import Buraq

        static = tmp_path / "static"
        static.mkdir(exist_ok=True)
        (static / name).write_bytes(body)
        if precompress:
            (static / f"{name}.gz").write_bytes(gzip.compress(body, 9))

        for key, value in {
            "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
            "SECRET_KEY": "x" * 32,
            "INSTALLED_APPS": [],
            "ROOT_URLCONF": None,
            "DEBUG": False,
            "SERVE_STATIC": True,
            "STATIC_DIR": str(static),
        }.items():
            monkeypatch.setattr(settings, key, value, raising=False)
        return TestClient(Buraq())

    return _serve


BODY = b"body { color: red; }\n" * 200


def test_a_precompressed_file_is_served_as_is(serve):
    with serve("a.css", BODY, precompress=True) as client:
        response = client.get("/static/a.css", headers={"Accept-Encoding": "gzip"})

    assert response.headers["content-encoding"] == "gzip"
    # The type is the original one: a browser asked for a stylesheet, not for
    # application/gzip.
    assert response.headers["content-type"].startswith("text/css")
    # Caches must key on the encoding or a gzip body reaches a client that
    # cannot read it.
    assert response.headers["vary"] == "Accept-Encoding"
    assert response.content == BODY


def test_a_client_that_cannot_decompress_gets_the_plain_file(serve):
    with serve("a.css", BODY, precompress=True) as client:
        response = client.get("/static/a.css", headers={"Accept-Encoding": "identity"})

    assert "content-encoding" not in response.headers
    assert response.content == BODY


def test_it_is_not_compressed_twice(serve):
    """
    GZipMiddleware used to compress an already-encoded response, producing
    "content-encoding: gzip, gzip" -- a body the browser unpacks twice, larger
    than the singly-encoded one.
    """
    with serve("a.css", BODY, precompress=True) as client:
        response = client.get("/static/a.css", headers={"Accept-Encoding": "gzip"})

    assert response.headers["content-encoding"] == "gzip"


def test_collectstatic_writes_the_compressed_copy(tmp_path):
    from buraq.contrib.staticfiles.storage import compress_file

    big = tmp_path / "big.css"
    big.write_bytes(BODY)
    assert compress_file(str(big)) is True
    assert gzip.decompress((tmp_path / "big.css.gz").read_bytes()) == BODY

    # Already-compressed formats gain nothing and cost a decompression.
    png = tmp_path / "logo.png"
    png.write_bytes(b"\x89PNG" + b"\x00" * 2000)
    assert compress_file(str(png)) is False
    assert not (tmp_path / "logo.png.gz").exists()
