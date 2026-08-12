"""
Usage:
    from buraq.http import HttpResponse, JsonResponse, Http404
    from buraq.http import HttpResponseRedirect, HttpResponseForbidden
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import orjson
from starlette.responses import Response
from starlette.responses import StreamingResponse as _StreamingResponse

# ── Base response ──────────────────────────────────────────────────────────────

class HttpResponse(Response):
    """
    Usage::

        return HttpResponse("<h1>Hello</h1>")
        return HttpResponse("Not found", status=404)
        return HttpResponse(b"binary", content_type="application/octet-stream")

    Supports dict-like header access::

        response = HttpResponse("OK")
        response["X-Custom-Header"] = "value"
        del response["X-Custom-Header"]
    """

    def __init__(
        self,
        content: str | bytes = "",
        content_type: str = "text/html; charset=utf-8",
        status: int = 200,
    ) -> None:
        if isinstance(content, str):
            content = content.encode("utf-8")
        super().__init__(content=content, status_code=status, media_type=content_type)

    def __setitem__(self, header: str, value: str) -> None:
        self.headers[header] = value

    def __delitem__(self, header: str) -> None:
        del self.headers[header]

    def __getitem__(self, header: str) -> str:
        return self.headers[header]

    def has_header(self, header: str) -> bool:
        return header in self.headers

    def set_cookie(
        self,
        key: str,
        value: str = "",
        max_age: int | None = None,
        expires: int | None = None,
        path: str = "/",
        domain: str | None = None,
        secure: bool = False,
        httponly: bool = False,
        samesite: str = "lax",
    ) -> None:
        super().set_cookie(
            key=key,
            value=value,
            max_age=max_age,
            expires=expires,
            path=path,
            domain=domain,
            secure=secure,
            httponly=httponly,
            samesite=samesite,
        )

    def delete_cookie(self, key: str, path: str = "/", domain: str | None = None) -> None:
        super().delete_cookie(key=key, path=path, domain=domain)


# ── JSON response ──────────────────────────────────────────────────────────────

class JsonResponse(HttpResponse):
    """
    An HTTP response with JSON-encoded body — uses orjson for Rust-speed serialization.

    Usage::

        return JsonResponse({"user": "alice", "score": 42})
        return JsonResponse([1, 2, 3], safe=False)
        return JsonResponse({"error": "not found"}, status=404)

    ``safe`` is ``False`` by default, allowing any JSON-serializable type.
    Set ``safe=True`` to restrict the top-level value to a dict.
    """

    def __init__(
        self,
        data: Any,
        safe: bool = False,
        status: int = 200,
        json_opts: int = 0,
    ) -> None:
        if safe and not isinstance(data, dict):
            raise TypeError(
                "In order to allow non-dict objects to be serialized set safe=False."
            )
        content = orjson.dumps(data, option=json_opts)
        super().__init__(content=content, content_type="application/json", status=status)


# ── Streaming response ─────────────────────────────────────────────────────────

class StreamingHttpResponse(_StreamingResponse):
    """
    Usage::

        async def stream():
            for chunk in large_dataset:
                yield chunk.encode()

        return StreamingHttpResponse(stream(), content_type="text/csv")
    """

    def __init__(
        self,
        streaming_content: AsyncIterator | Iterator,
        content_type: str = "text/html; charset=utf-8",
        status: int = 200,
    ) -> None:
        super().__init__(content=streaming_content, status_code=status, media_type=content_type)

    def __setitem__(self, header: str, value: str) -> None:
        self.headers[header] = value

    def __delitem__(self, header: str) -> None:
        del self.headers[header]


# ── Redirect responses ─────────────────────────────────────────────────────────

class HttpResponseRedirect(HttpResponse):
    """302 redirect."""
    def __init__(self, redirect_to: str) -> None:
        super().__init__(status=302)
        self["Location"] = redirect_to


class HttpResponsePermanentRedirect(HttpResponse):
    """301 permanent redirect."""
    def __init__(self, redirect_to: str) -> None:
        super().__init__(status=301)
        self["Location"] = redirect_to


# ── Client error responses ─────────────────────────────────────────────────────

class HttpResponseNotModified(HttpResponse):
    """304 Not Modified — no body."""
    def __init__(self) -> None:
        super().__init__(status=304)


class HttpResponseBadRequest(HttpResponse):
    """400 Bad Request."""
    def __init__(self, content: str = "") -> None:
        super().__init__(content=content, status=400)


class HttpResponseNotFound(HttpResponse):
    """404 Not Found."""
    def __init__(self, content: str = "") -> None:
        super().__init__(content=content, status=404)


class HttpResponseForbidden(HttpResponse):
    """403 Forbidden."""
    def __init__(self, content: str = "") -> None:
        super().__init__(content=content, status=403)


class HttpResponseNotAllowed(HttpResponse):
    """405 Method Not Allowed. Pass the list of permitted methods."""
    def __init__(self, permitted_methods: list[str]) -> None:
        super().__init__(status=405)
        self["Allow"] = ", ".join(permitted_methods)


class HttpResponseGone(HttpResponse):
    """410 Gone."""
    def __init__(self, content: str = "") -> None:
        super().__init__(content=content, status=410)


class HttpResponseServerError(HttpResponse):
    """500 Internal Server Error."""
    def __init__(self, content: str = "") -> None:
        super().__init__(content=content, status=500)


# ── Exception ──────────────────────────────────────────────────────────────────

class FileResponse(HttpResponse):
    """
    Serve a file from disk with the correct Content-Type and Content-Disposition.

    Usage::

        return FileResponse("/path/to/report.pdf")
        return FileResponse("/path/to/data.csv", filename="export.csv")
        return FileResponse("/path/to/image.png", as_attachment=False)

    ``as_attachment=True`` (default) sets ``Content-Disposition: attachment``
    so the browser downloads the file rather than rendering it inline.
    Set ``as_attachment=False`` for inline display (e.g. images, PDFs in a viewer).
    """

    def __init__(
        self,
        file_path: str,
        filename: str | None = None,
        as_attachment: bool = True,
        content_type: str | None = None,
    ) -> None:
        import mimetypes
        from pathlib import Path

        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"FileResponse: {file_path!r} does not exist.")

        data = path.read_bytes()
        name = filename or path.name

        if content_type is None:
            guessed, _ = mimetypes.guess_type(name)
            content_type = guessed or "application/octet-stream"

        super().__init__(content=data, content_type=content_type, status=200)

        disposition = "attachment" if as_attachment else "inline"
        self["Content-Disposition"] = f'{disposition}; filename="{name}"'
        self["Content-Length"] = str(len(data))


class Http404(Exception):
    """
    Raise this inside a view to return a 404 response.
    Buraq registers an exception handler for it automatically.

    Usage::

        from buraq.http import Http404

        async def post_detail(request, pk: int):
            post = await Post.objects.get_or_none(id=pk)
            if post is None:
                raise Http404(f"Post {pk} not found")
            ...
    """
