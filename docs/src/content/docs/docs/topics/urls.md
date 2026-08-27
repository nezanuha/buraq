---
title: "URLs"
description: "Buraq supports two styles for defining URL patterns — Django-style path() (recommended) and FastAPI-style per-method helpers."
---

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

## Namespaced includes

```python
path("/auth",  include("buraq.contrib.auth.urls", namespace="auth"))
path("/posts", include("posts.urls", namespace="posts"))
```

Then `reverse()` uses the namespace:
```python
reverse("auth:login")
reverse("posts:post_detail", pk=42)
```

## Including sub-applications

```python title="config/urls.py"
from buraq.urls import path, include

urlpatterns = [
    path("/auth",   include("buraq.contrib.auth.urls")),
    path("/posts",  include("posts.urls")),
    path("/api/v1", include("api.urls")),
]
```

## path() with extra view kwargs

```python
# Pass a dict as the third positional argument — forwarded to the view
path("/posts", views.post_list, {"template": "posts/custom.html"}, name="post_list")

# Equivalent using functools.partial:
from functools import partial
path("/posts", partial(views.post_list, template="posts/custom.html"), name="post_list")
```

## i18n_patterns prefix_default_language

```python
urlpatterns = [
    i18n_patterns(
        path("/", views.home, name="home"),
        prefix_default_language=False,  # default language served at /, not /en/
    ),
]
```

When `prefix_default_language=False`:
- Default language (`LANGUAGE_CODE`) → `/about`
- Other languages → `/ar/about`, `/fr/about`

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

## Reversing URLs

### reverse

```python
from buraq.urls import reverse

url = reverse("post_detail", pk=1)   # → "/posts/1"
url = reverse("auth:login")          # namespaced route
```

Raises `NoReverseMatch` if the name is not registered or a required path parameter is missing.

### reverse_lazy

```python
from buraq.urls import reverse_lazy

# Safe to use at class body level — URL not resolved until first use
class PostCreateView(CreateView):
    success_url = reverse_lazy("post_list")
```

Evaluates to the same string as `reverse()` but deferred until the value is coerced to `str`. Use it anywhere the URL registry may not be fully populated at import time: CBV class attributes, module-level constants, default argument values.

## re_path — regex URL patterns

When `path()` converters aren't expressive enough, use `re_path()` with a raw regular expression:

```python
from buraq.urls import re_path

urlpatterns = [
    re_path(r"^articles/(?P<year>[0-9]{4})/$", views.year_archive, name="article-year"),
    re_path(r"^articles/(?P<year>[0-9]{4})/(?P<month>[0-9]{2})/$", views.month_archive),
]
```

Named capture groups (`?P<name>`) are passed as keyword arguments to the view.

## resolve() — reverse path lookup

Resolve a URL path back to the view function that handles it:

```python
from buraq.urls import resolve, Resolver404

try:
    match = resolve("/posts/hello-world/")   # → ResolverMatch
    # match.func      → the view callable
    # match.args      → positional arguments
    # match.kwargs    → keyword arguments {"slug": "hello-world"}
    # match.url_name  → "post_detail" (if named)
    # match.app_name  → namespace (if any)
except Resolver404:
    print("No URL pattern matched this path")
```

`resolve()` raises `Resolver404` if no pattern matches.

## Exceptions

| Exception | When raised |
|---|---|
| `NoReverseMatch` | `reverse()` / `reverse_lazy()` cannot build a URL from the given name and arguments |
| `Resolver404` | `resolve()` cannot find a matching URL pattern |

```python
from buraq.urls import reverse, NoReverseMatch

try:
    url = reverse("nonexistent-view", pk=99)
except NoReverseMatch as e:
    return HttpResponseNotFound(str(e))
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
