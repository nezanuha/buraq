# URLs

## Defining URL patterns

Buraq supports two styles for defining URL patterns — Django-style `path()` (recommended) and FastAPI-style per-method helpers.

### Django-style (recommended)

`path()` accepts **all HTTP methods** by default. Method dispatch is handled inside the view or CBV, exactly like Django:

```python title="posts/urls.py"
from buraq.urls import path
from posts import views

urlpatterns = [
    path("/",            views.post_list,                name="post_list"),
    path("/new",         views.PostCreateView.as_view(), name="post_create"),
    path("/<str:slug>/", views.post_detail,              name="post_detail"),
    path("/<int:pk>/edit",   views.PostUpdateView.as_view(), name="post_update"),
    path("/<int:pk>/delete", views.PostDeleteView.as_view(), name="post_delete"),
]
```

### FastAPI-style (per-method)

If you prefer explicit per-method registration (useful for pure JSON APIs), use the method helpers:

```python title="posts/urls.py"
from buraq.urls import get, post, put, patch, delete
from posts import views

urlpatterns = [
    get("/",               views.post_list,   name="post_list"),
    post("/",              views.create_post, name="post_create", status_code=201),
    get("/<int:pk>",       views.post_detail, name="post_detail"),
    put("/<int:pk>",       views.update_post, name="post_update"),
    patch("/<int:pk>",     views.update_post),
    delete("/<int:pk>",    views.delete_post, name="post_delete", status_code=204),
]
```

## Including sub-applications

```python title="config/urls.py"
from buraq import Buraq
from buraq.urls import path, include

app = Buraq(settings_module="config.settings")

urlpatterns = [
    path("/auth",   include("buraq.contrib.auth.urls")),
    path("/posts",  include("posts.urls")),
    path("/api/v1", include("api.urls")),
]

app.load_urls(urlpatterns)
```

## Path converters

| Converter | Example | Python type |
|---|---|---|
| `<int:pk>` | `/posts/42` | `int` |
| `<str:name>` | `/users/alice` | `str` |
| `<slug:slug>` | `/posts/hello-world` | `str` |
| `<uuid:uid>` | `/items/abc-123` | `str` |
| `<path:rest>` | `/files/a/b/c.txt` | `str` |

FastAPI-style paths also work: `{pk}`, `{slug}`.

## Named routes

Use `name=` to generate URLs from route names in templates:

```html+jinja
<a href="{{ url_for('post_detail', pk=post.id) }}">{{ post.title }}</a>
```

## Extra route options

Any extra keyword arguments are passed to FastAPI's route decorator:

```python
get("/posts/", views.post_list,
    name="post_list",
    status_code=200,
    tags=["posts"],
    summary="List all published posts",
    response_model=list[PostSchema],
)
```

## HTTP method helpers

| Function | HTTP methods | Notes |
|---|---|---|
| `path(path, view)` | ALL | Django-style; dispatch inside view |
| `path(path, view, methods=["GET","POST"])` | specified | Restrict methods explicitly |
| `get(path, view)` | GET | FastAPI-style helper |
| `post(path, view)` | POST | FastAPI-style helper |
| `put(path, view)` | PUT | FastAPI-style helper |
| `patch(path, view)` | PATCH | FastAPI-style helper |
| `delete(path, view)` | DELETE | FastAPI-style helper |
