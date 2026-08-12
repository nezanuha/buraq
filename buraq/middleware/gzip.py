"""
GZipMiddleware — compresses responses with gzip when the client supports it.

Usage::

    MIDDLEWARE = [
        ...
        "buraq.middleware.gzip.GZipMiddleware",
    ]
"""
from __future__ import annotations

import gzip
import io


class GZipMiddleware:
    """
    Compresses response bodies with gzip when:

    - The client sends ``Accept-Encoding: gzip``
    - The response is larger than ``min_length`` bytes (default 200)
    - The response ``Content-Type`` is compressible (text/*, application/json, etc.)
    """

    compressible_types = frozenset({
        "text/plain", "text/html", "text/css", "text/javascript",
        "application/json", "application/javascript", "application/xml",
        "image/svg+xml",
    })

    def __init__(self, app, min_length: int = 200):
        self.app = app
        self.min_length = min_length

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_headers = dict(scope.get("headers", []))
        accept_encoding = request_headers.get(b"accept-encoding", b"").decode()
        if "gzip" not in accept_encoding:
            await self.app(scope, receive, send)
            return

        body_chunks: list[bytes] = []
        initial_response = {}

        async def capture_send(message):
            if message["type"] == "http.response.start":
                initial_response["status"] = message["status"]
                initial_response["headers"] = list(message.get("headers", []))
            elif message["type"] == "http.response.body":
                body_chunks.append(message.get("body", b""))

        await self.app(scope, receive, capture_send)

        body = b"".join(body_chunks)
        content_type = ""
        for k, v in initial_response.get("headers", []):
            if k.lower() == b"content-type":
                content_type = v.decode().split(";")[0].strip()
                break

        should_compress = (
            len(body) >= self.min_length
            and any(content_type.startswith(ct) for ct in self.compressible_types)
        )

        if should_compress:
            buf = io.BytesIO()
            with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
                gz.write(body)
            body = buf.getvalue()
            headers = [
                (k, v) for k, v in initial_response.get("headers", [])
                if k.lower() not in (b"content-length",)
            ]
            headers.append((b"content-encoding", b"gzip"))
            headers.append((b"content-length", str(len(body)).encode()))
        else:
            headers = initial_response.get("headers", [])

        await send({
            "type": "http.response.start",
            "status": initial_response.get("status", 200),
            "headers": headers,
        })
        await send({"type": "http.response.body", "body": body})
