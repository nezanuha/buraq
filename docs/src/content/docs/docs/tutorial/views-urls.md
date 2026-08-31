---
title: "Part 2 — Views & URLs"
description: "path() handles all HTTP methods, so GET and POST for the same URL are registered once. Method dispatch happens inside the CBV (via get() / post() handlers)…"
---

A view is a coroutine that takes a request and returns a response. Buraq has
two ways to write one, and they route identically — pick per view, not per
project.

## Function-Based Views

Best when the view does one thing. Everything is visible in the function.

```python title="posts/views.py"
from buraq.shortcuts import render, redirect, get_object_or_404
from posts.models import Post, Comment


async def post_list(request):
    posts = await Post.objects.filter(is_published=True).order_by("-created_at")
    return await render(request, "posts/list.html", {"posts": posts})


async def post_detail(request, slug: str):
    post     = await get_object_or_404(Post, slug=slug)
    comments = await Comment.objects.filter(post_id=post.id).order_by("created_at")
    return await render(request, "posts/detail.html", {"post": post, "comments": comments})
```

## Class-Based Views

Best for the five views every model ends up needing. Each generic view already
knows how to list, show, create, update or delete, so a subclass is mostly
configuration.

`PostForm` arrives in [Part 3](forms.md) — leave the create and update views
out until then, or the import will fail.

```python title="posts/views.py"
from buraq.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from posts.models import Post
from posts.forms import PostForm


class PostListView(ListView):
    model        = Post
    template_name = "posts/list.html"
    paginate_by  = 10

    async def get_queryset(self):
        return await Post.objects.filter(is_published=True).order_by("-created_at")


class PostDetailView(DetailView):
    model         = Post
    template_name = "posts/detail.html"


class PostCreateView(CreateView):
    model         = Post
    form_class    = PostForm
    template_name = "posts/form.html"
    success_url   = "/posts/"


class PostUpdateView(UpdateView):
    model         = Post
    form_class    = PostForm
    template_name = "posts/form.html"
    success_url   = "/posts/"


class PostDeleteView(DeleteView):
    model         = Post
    template_name = "posts/confirm_delete.html"
    success_url   = "/posts/"
```

## URL Configuration

`path()` handles all HTTP methods, so GET and POST for the same URL are
registered once. Method dispatch happens inside the view — a class-based view
routes to its `get()` and `post()` handlers, and a function view reads
`request.method`.

```python title="posts/urls.py"
from buraq.urls import path
from posts import views

urlpatterns = [
    path("/",                views.PostListView.as_view(),   name="post_list"),
    path("/new",             views.PostCreateView.as_view(), name="post_create"),
    path("/<int:pk>/edit",   views.PostUpdateView.as_view(), name="post_update"),
    path("/<int:pk>/delete", views.PostDeleteView.as_view(), name="post_delete"),
    path("/<str:slug>",      views.PostDetailView.as_view(), name="post_detail"),
]
```

**Order matters, and only in one direction.** Routes are matched top to bottom,
so anything with a converter in it has to come after the fixed paths it could
swallow. With `/<str:slug>` listed first, `/posts/new` matches *it* — the slug
is `"new"` — and the create page can never be reached. Fixed segments first,
converters last, and the list reads in the order a request is tried.

```python title="config/urls.py"
from buraq.urls import path, include

urlpatterns = [
    path("/posts", include("posts.urls")),
]
```

Every path in `posts/urls.py` is relative to the `/posts` prefix given here, so
`path("/new", ...)` is served at `/posts/new`. Mounting the same app somewhere
else is a one-line change, which is why the views above redirect through
`reverse()` rather than writing `/posts/` into the code.

## URL path syntax

Buraq supports Django-style path converters:

| Pattern | Matches | Example |
|---|---|---|
| `<int:pk>` | Integer | `/posts/42` |
| `<str:slug>` | String (no `/`) | `/posts/hello-world` |
| `<slug:slug>` | Slug characters | `/posts/hello-world` |
| `<uuid:uid>` | UUID | `/posts/abc-123-...` |
| `<path:rest>` | Any path | `/files/a/b/c` |

The templates these views name — `posts/list.html`, `posts/detail.html`,
`posts/form.html`, `posts/confirm_delete.html` — go under the project's
`templates/` directory or the app's own. [Part 4](templates.md) writes them.

Next: [Forms →](forms.md)
