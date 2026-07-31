# buraq.urls — API Reference

```python
from buraq.urls import get, post, put, patch, delete, path, include
```

## Route functions

```python
get(url_path, view, name="", **extra)
post(url_path, view, name="", **extra)
put(url_path, view, name="", **extra)
patch(url_path, view, name="", **extra)
delete(url_path, view, name="", **extra)
```

| Param | Description |
|---|---|
| `url_path` | Path string — Django (`/<int:pk>`) or FastAPI (`/{pk}`) style |
| `view` | Async function or `View.as_view()` result |
| `name` | Route name for `url_for()` in templates |
| `**extra` | Passed to FastAPI's route decorator (`status_code`, `tags`, `response_model`, etc.) |

## path

```python
path(url_path, view_or_include, name="", **extra)
path(url_path, view_or_include, name="", methods=["GET", "POST"])  # restrict methods
```

Django-style route helper. Defaults to accepting **all HTTP methods** — `GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS`. Method dispatch is handled inside the view or CBV. Pass an explicit `methods=` list to restrict. Also accepts an `include()` object instead of a view.

## include

```python
include(module_path: str) -> URLInclude
```

Include URL patterns from another module.

```python
path("/posts", include("posts.urls"))
```

## register_urlpatterns

```python
register_urlpatterns(app, patterns, prefix="")
```

Called internally by `app.load_urls()`. Recursively registers all `URLPattern` and `URLInclude` objects with the FastAPI app.

## URLPattern

```python
@dataclass
class URLPattern:
    path:        str         # FastAPI-style path, e.g. /posts/{pk}
    view:        Callable
    name:        str
    methods:     list[str]   # ["GET"]
    extra:       dict
    param_types: dict        # {"pk": int} — extracted from Django-style converters
```
