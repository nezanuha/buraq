# Part 2 — Views & URLs

## Function-Based Views

```python title="posts/views.py"
from buraq.shortcuts import render, redirect, get_object_or_404
from posts.models import Post, Comment


async def post_list(request):
    posts = await Post.objects.filter(is_published=True).order_by("-created_at")
    return render(request, "posts/list.html", {"posts": posts})


async def post_detail(request, slug: str):
    post     = await get_object_or_404(Post, slug=slug)
    comments = await Comment.objects.filter(post_id=post.id).order_by("created_at")
    return render(request, "posts/detail.html", {"post": post, "comments": comments})
```

## Class-Based Views

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

`path()` handles all HTTP methods, so GET and POST for the same URL are registered once. Method dispatch happens inside the CBV (via `get()` / `post()` handlers), exactly like Django:

```python title="posts/urls.py"
from buraq.urls import path
from posts import views

urlpatterns = [
    path("/",                    views.PostListView.as_view(),   name="post_list"),
    path("/<str:slug>",          views.PostDetailView.as_view(), name="post_detail"),
    path("/new",                 views.PostCreateView.as_view(), name="post_create"),
    path("/<int:pk>/edit",       views.PostUpdateView.as_view(), name="post_update"),
    path("/<int:pk>/delete",     views.PostDeleteView.as_view(), name="post_delete"),
]
```

```python title="config/urls.py"
from buraq import Buraq
from buraq.urls import path, include

app = Buraq(settings_module="config.settings")

urlpatterns = [
    path("/posts", include("posts.urls")),
]

app.load_urls(urlpatterns)
```

## URL path syntax

Buraq supports Django-style path converters:

| Pattern | Matches | Example |
|---|---|---|
| `<int:pk>` | Integer | `/posts/42` |
| `<str:slug>` | String (no `/`) | `/posts/hello-world` |
| `<slug:slug>` | Slug characters | `/posts/hello-world` |
| `<uuid:uid>` | UUID | `/posts/abc-123-...` |
| `<path:rest>` | Any path | `/files/a/b/c` |

Next: [Forms →](forms.md)
