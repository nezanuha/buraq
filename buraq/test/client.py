"""
AsyncClient and RequestFactory for testing Buraq views.

``AsyncClient``    — makes HTTP requests through the ASGI app in-process
``RequestFactory`` — builds raw Request objects without sending them
"""
from __future__ import annotations

import json as _json
import urllib.parse
from http.cookies import SimpleCookie
from typing import Any


class _FakeReceive:
    """ASGI ``receive`` callable that returns a pre-built body."""

    def __init__(self, body: bytes = b""):
        self._body = body
        self._sent = False

    async def __call__(self):
        if not self._sent:
            self._sent = True
            return {"type": "http.request", "body": self._body, "more_body": False}
        return {"type": "http.disconnect"}


class _ResponseCapture:
    """ASGI ``send`` callable that captures the response."""

    def __init__(self):
        self.status_code: int = 200
        self.headers: dict[str, str] = {}
        self._body_parts: list[bytes] = []

    async def __call__(self, message: dict) -> None:
        if message["type"] == "http.response.start":
            self.status_code = message["status"]
            self.headers = {
                k.decode(): v.decode()
                for k, v in message.get("headers", [])
            }
        elif message["type"] == "http.response.body":
            self._body_parts.append(message.get("body", b""))

    @property
    def content(self) -> bytes:
        return b"".join(self._body_parts)

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return _json.loads(self.content)

    @property
    def cookies(self) -> SimpleCookie:
        jar = SimpleCookie()
        for value in self.headers.get("set-cookie", "").split(", "):
            if value:
                jar.load(value)
        return jar

    def __repr__(self):
        return f"<Response {self.status_code}>"


class AsyncClient:
    """
    Test client that exercises the full ASGI stack in-process — no server needed.

    Pass your Buraq ``app`` instance to the constructor, or omit it to have
    the client import the app from ``config.urls`` automatically.

    Usage::

        from buraq.test import AsyncClient

        async def test_index(app):
            client = AsyncClient(app)
            response = await client.get("/")
            assert response.status_code == 200
            assert "Welcome" in response.text
    """

    def __init__(self, app=None):
        self._app = app
        self._cookies: dict[str, str] = {}
        self._session: dict = {}

    def _get_app(self):
        if self._app is None:
            try:
                from config.urls import app
                self._app = app
            except ImportError as exc:
                raise RuntimeError(
                    "Pass your Buraq app to AsyncClient(app=...) or ensure "
                    "config/urls.py exposes an 'app' object."
                ) from exc
        return self._app

    async def _request(
        self,
        method: str,
        path: str,
        *,
        data: dict | bytes | str | None = None,
        content_type: str = "application/x-www-form-urlencoded",
        headers: dict | None = None,
        json: Any = None,
        follow_redirects: bool = False,
    ) -> _ResponseCapture:
        # Build body
        if json is not None:
            body = _json.dumps(json).encode()
            content_type = "application/json"
        elif isinstance(data, bytes):
            body = data
        elif isinstance(data, str):
            body = data.encode()
        elif isinstance(data, dict):
            body = urllib.parse.urlencode(data).encode()
        else:
            body = b""

        # Parse path/query
        parsed = urllib.parse.urlsplit(path)
        raw_path = parsed.path.encode()
        query_string = parsed.query.encode()

        # Build cookie header
        cookie_header = "; ".join(f"{k}={v}" for k, v in self._cookies.items())

        scope_headers: list[tuple[bytes, bytes]] = [
            (b"content-type", content_type.encode()),
            (b"content-length", str(len(body)).encode()),
        ]
        if cookie_header:
            scope_headers.append((b"cookie", cookie_header.encode()))
        for k, v in (headers or {}).items():
            scope_headers.append((k.lower().encode(), v.encode()))

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method.upper(),
            "headers": scope_headers,
            "path": parsed.path,
            "raw_path": raw_path,
            "query_string": query_string,
            "root_path": "",
            "scheme": "http",
            "server": ("testserver", 80),
        }

        receive = _FakeReceive(body)
        capture = _ResponseCapture()

        await self._get_app()(scope, receive, capture)

        # Persist cookies from response
        for name, morsel in capture.cookies.items():
            self._cookies[name] = morsel.value

        if follow_redirects and capture.status_code in (301, 302, 303, 307, 308):
            location = capture.headers.get("location", "")
            if location:
                return await self._request("GET", location, follow_redirects=follow_redirects)

        return capture

    async def get(self, path: str, **kwargs) -> _ResponseCapture:
        return await self._request("GET", path, **kwargs)

    async def post(self, path: str, data=None, **kwargs) -> _ResponseCapture:
        return await self._request("POST", path, data=data, **kwargs)

    async def put(self, path: str, data=None, **kwargs) -> _ResponseCapture:
        return await self._request("PUT", path, data=data, **kwargs)

    async def patch(self, path: str, data=None, **kwargs) -> _ResponseCapture:
        return await self._request("PATCH", path, data=data, **kwargs)

    async def delete(self, path: str, **kwargs) -> _ResponseCapture:
        return await self._request("DELETE", path, **kwargs)

    async def head(self, path: str, **kwargs) -> _ResponseCapture:
        return await self._request("HEAD", path, **kwargs)

    async def options(self, path: str, **kwargs) -> _ResponseCapture:
        return await self._request("OPTIONS", path, **kwargs)

    def force_login(self, user) -> None:
        """Inject a session cookie so the client acts as ``user`` on every request."""
        self._cookies["_auth_user_id"] = str(user.id)


class RequestFactory:
    """
    Build ``starlette.requests.Request`` objects without a running server.

    Useful for unit-testing views directly without going through the ASGI stack.

    Usage::

        from buraq.test import RequestFactory

        factory = RequestFactory()
        request = factory.get("/posts/", {"page": "2"})
        response = await my_view(request)
        assert response.status_code == 200
    """

    def __init__(self, base_url: str = "http://testserver"):
        self.base_url = base_url.rstrip("/")

    def _build_scope(
        self,
        method: str,
        path: str,
        data: dict | bytes | None = None,
        content_type: str = "application/x-www-form-urlencoded",
        headers: dict | None = None,
        json: Any = None,
    ) -> tuple[dict, bytes]:
        from urllib.parse import urlencode, urlsplit

        if json is not None:
            body = _json.dumps(json).encode()
            content_type = "application/json"
        elif isinstance(data, bytes):
            body = data
        elif isinstance(data, dict) and method.upper() == "GET":
            body = b""
            path = f"{path}?{urlencode(data)}"
        elif isinstance(data, dict):
            body = urlencode(data).encode()
        else:
            body = b""

        parsed = urlsplit(path)
        scope_headers: list[tuple[bytes, bytes]] = [
            (b"content-type", content_type.encode()),
            (b"content-length", str(len(body)).encode()),
        ]
        for k, v in (headers or {}).items():
            scope_headers.append((k.lower().encode(), v.encode()))

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method.upper(),
            "headers": scope_headers,
            "path": parsed.path,
            "raw_path": parsed.path.encode(),
            "query_string": parsed.query.encode(),
            "root_path": "",
            "scheme": "http",
            "server": ("testserver", 80),
        }
        return scope, body

    def _make_request(self, method: str, path: str, data=None, **kwargs):
        from starlette.requests import Request

        scope, body = self._build_scope(method, path, data=data, **kwargs)
        receive = _FakeReceive(body)

        return Request(scope, receive)

    def get(self, path: str, data: dict | None = None, **kwargs):
        return self._make_request("GET", path, data=data, **kwargs)

    def post(self, path: str, data=None, **kwargs):
        return self._make_request("POST", path, data=data, **kwargs)

    def put(self, path: str, data=None, **kwargs):
        return self._make_request("PUT", path, data=data, **kwargs)

    def patch(self, path: str, data=None, **kwargs):
        return self._make_request("PATCH", path, data=data, **kwargs)

    def delete(self, path: str, **kwargs):
        return self._make_request("DELETE", path, **kwargs)
