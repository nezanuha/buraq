"""
A file response must survive GZipMiddleware on a server that supports pathsend.

Granian -- the server Buraq ships and starts by default -- advertises the
``http.response.pathsend`` ASGI extension, so Starlette's FileResponse hands the
path to the server instead of writing a body. A middleware that buffers only
``http.response.body`` messages silently drops the entire response: the client
gets 200 with zero bytes. Every browser sends ``Accept-Encoding: gzip``, so this
affected every file served to every real client.
"""

import gzip

import pytest
from starlette.responses import FileResponse, HTMLResponse

from buraq.middleware.gzip import GZipMiddleware


async def _run(app, *, extensions, accept_gzip=True):
    """Drive one request through the middleware, returning (start, messages)."""
    sent = []
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/f",
        "headers": [(b"accept-encoding", b"gzip")] if accept_gzip else [],
        "extensions": extensions,
    }

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.disconnect"}

    await GZipMiddleware(app)(scope, receive, send)
    return sent


@pytest.fixture
def css_file(tmp_path):
    path = tmp_path / "site.css"
    path.write_text("body{color:red}\n" * 50)
    return path


async def test_pathsend_response_is_forwarded(css_file):
    """With pathsend available the middleware must not swallow the response."""

    async def app(scope, receive, send):
        await FileResponse(css_file)(scope, receive, send)

    sent = await _run(app, extensions={"http.response.pathsend": {}})

    types = [m["type"] for m in sent]
    assert "http.response.start" in types
    assert "http.response.pathsend" in types, (
        "the pathsend message was dropped -- the client would receive an empty body"
    )
    # The server serves the file; the middleware must not have replaced it with
    # an empty body of its own.
    assert not any(m.get("body") == b"" and m["type"] == "http.response.body" for m in sent)


async def test_file_still_sent_without_pathsend(css_file):
    """Servers without the extension still get a real body."""

    async def app(scope, receive, send):
        await FileResponse(css_file)(scope, receive, send)

    sent = await _run(app, extensions={})
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    assert len(body) > 0


async def test_html_is_still_compressed():
    """The fix must not stop the middleware doing its actual job."""

    async def app(scope, receive, send):
        await HTMLResponse("<h1>hello</h1>" * 100)(scope, receive, send)

    sent = await _run(app, extensions={})
    start = next(m for m in sent if m["type"] == "http.response.start")
    headers = {k.lower(): v for k, v in start["headers"]}
    assert headers.get(b"content-encoding") == b"gzip"

    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    assert gzip.decompress(body).startswith(b"<h1>hello</h1>")


async def test_incompressible_response_streams_rather_than_buffers():
    """A large binary body should pass through in its original chunks."""
    chunks = [b"x" * 1024, b"y" * 1024, b"z" * 1024]

    async def app(scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"video/mp4")],
        })
        for i, chunk in enumerate(chunks):
            await send({
                "type": "http.response.body",
                "body": chunk,
                "more_body": i < len(chunks) - 1,
            })

    sent = await _run(app, extensions={})
    bodies = [m["body"] for m in sent if m["type"] == "http.response.body"]
    assert bodies == chunks, "an incompressible body was buffered instead of streamed"
