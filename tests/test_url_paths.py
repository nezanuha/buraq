"""
Typed URL path conversion.

`path("/posts/<int:pk>", ...)` must convert to FastAPI's `{pk}` syntax *and*
yield the parameter's Python type, so the route coerces `pk` to an int.

Regression: the module-level regex for typed params once shared a name with a
different regex defined later in the same file. The later definition shadowed
it, so type extraction silently returned `{}` — paths still routed, but every
parameter arrived as a string.
"""

import pytest

from buraq.urls import _extract_param_types, _to_fastapi_path


@pytest.mark.parametrize(
    "url_path,expected",
    [
        ("/posts/<int:pk>", "/posts/{pk}"),
        ("posts/<int:pk>/", "/posts/{pk}"),
        ("blog/<slug:slug>", "/blog/{slug}"),
        ("<str:name>/", "/{name}"),
        ("<uuid:uid>", "/{uid}"),
        ("/posts/<int:pk>/<slug:name>", "/posts/{pk}/{name}"),
        ("/static", "/static"),
    ],
)
def test_typed_paths_convert_to_fastapi_syntax(url_path, expected):
    assert _to_fastapi_path(url_path) == expected


@pytest.mark.parametrize(
    "url_path,expected",
    [
        ("/posts/<int:pk>", {"pk": int}),
        ("/posts/<int:pk>/<slug:name>", {"pk": int, "name": str}),
        ("/blog/<slug:slug>", {"slug": str}),
        ("/f/<uuid:uid>", {"uid": str}),
        ("/f/<path:rest>", {"rest": str}),
        ("/no/params", {}),
    ],
)
def test_param_types_are_extracted(url_path, expected):
    assert _extract_param_types(url_path) == expected


def test_int_converter_yields_int_not_str():
    """The whole point: `<int:pk>` must coerce, not arrive as a string."""
    assert _extract_param_types("/posts/<int:pk>")["pk"] is int


def test_unknown_converter_falls_back_to_str():
    assert _extract_param_types("/x/<weird:thing>") == {"thing": str}
