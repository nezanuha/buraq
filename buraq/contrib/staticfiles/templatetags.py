"""
Jinja2 extension providing Django-style {% static %} and {% media %} tags.

Registered automatically by Buraq — no {% load %} needed.

Usage in templates::

    {% static 'css/style.css' %}
    {% static 'js/app.js' %}
    {% media 'uploads/photo.jpg' %}

These are equivalent to the function-call forms::

    {{ static('css/style.css') }}
    {{ media('uploads/photo.jpg') }}

Both forms return the correct URL — hashed when ManifestStaticFilesStorage is active.
"""
from __future__ import annotations

from jinja2 import nodes
from jinja2.ext import Extension


class StaticExtension(Extension):
    """Adds ``{% static 'path' %}`` and ``{% media 'path' %}`` to Jinja2 templates."""

    tags = {"static", "media"}

    def parse(self, parser):
        tag = parser.stream.current.value
        lineno = next(parser.stream).lineno
        path_node = parser.parse_expression()

        if tag == "static":
            call = self.call_method("_static_url", [path_node])
        else:
            call = self.call_method("_media_url", [path_node])

        return nodes.Output([nodes.MarkSafe(call)], lineno=lineno)

    def _static_url(self, path: str) -> str:
        try:
            from buraq.contrib.staticfiles.storage import get_storage
            return get_storage().url(path)
        except Exception:
            from buraq.conf import settings
            return settings.STATIC_URL.rstrip("/") + "/" + path.lstrip("/")

    def _media_url(self, path: str) -> str:
        from buraq.conf import settings
        return settings.MEDIA_URL.rstrip("/") + "/" + path.lstrip("/")
