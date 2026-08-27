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

    Responses that fail any of those tests are streamed straight through rather
    than buffered, so a large download does not sit in memory on its way past.
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

        start_message: dict | None = None
        body_chunks: list[bytes] = []
        state = {"streaming": False, "started": False}

        async def capture_send(message):
            nonlocal start_message
            message_type = message["type"]

            if message_type == "http.response.start":
                start_message = message
                content_type = ""
                already_encoded = False
                for k, v in message.get("headers", []):
                    key = k.lower()
                    if key == b"content-type":
                        content_type = v.decode().split(";")[0].strip()
                    elif key == b"content-encoding" and v.strip():
                        # Something downstream already compressed this -- a
                        # pre-compressed static file, say. Compressing it again
                        # produces "content-encoding: gzip, gzip", which a
                        # browser has to unpack twice, for a body that is now
                        # larger than the single-encoded one.
                        already_encoded = True
                if already_encoded or not any(
                    content_type.startswith(ct) for ct in self.compressible_types
                ):
                    # Nothing to gain by holding this. Let it stream.
                    state["streaming"] = True
                    state["started"] = True
                    await send(message)

            elif message_type == "http.response.pathsend":
                # The server sends this file from disk itself, so no body ever
                # reaches this middleware. Buffering here would swallow the
                # response whole -- the client gets 200 and zero bytes. Forward
                # it untouched and let the server do its job.
                if not state["started"]:
                    state["started"] = True
                    await send(start_message)
                state["streaming"] = True
                await send(message)

            elif state["streaming"]:
                await send(message)

            else:
                body_chunks.append(message.get("body", b""))

        await self.app(scope, receive, capture_send)

        if state["streaming"] or start_message is None:
            return

        body = b"".join(body_chunks)
        if len(body) >= self.min_length:
            buf = io.BytesIO()
            with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
                gz.write(body)
            body = buf.getvalue()
            headers = [
                (k, v) for k, v in start_message.get("headers", [])
                if k.lower() != b"content-length"
            ]
            headers.append((b"content-encoding", b"gzip"))
            headers.append((b"content-length", str(len(body)).encode()))
        else:
            headers = start_message.get("headers", [])

        await send({
            "type": "http.response.start",
            "status": start_message.get("status", 200),
            "headers": headers,
        })
        await send({"type": "http.response.body", "body": body})
