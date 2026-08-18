---
title: "Quickstart"
description: "Visit http://127.0.0.1:8000/posts/ — your blog is live."
---

Build a working blog API in 5 minutes.

## 1. Create a project

```bash
buraq startproject myblog
cd myblog
uv sync
```

## 2. Create an app

```bash
buraq startapp posts
```

## 3. Define a model

```python title="posts/models.py"
from buraq import models


class Post(models.Model):
    title        = models.CharField(max_length=200)
    slug         = models.SlugField(max_length=200, unique=True)
    content      = models.TextField()
    is_published = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)
```

## 4. Write views

```python title="posts/views.py"
from buraq.shortcuts import render, redirect, get_object_or_404
from posts.models import Post


async def post_list(request):
    posts = await Post.objects.filter(is_published=True).order_by("-created_at")
    return await render(request, "posts/list.html", {"posts": posts})


async def post_detail(request, slug: str):
    post = await get_object_or_404(Post, slug=slug)
    return await render(request, "posts/detail.html", {"post": post})
```

## 5. Wire up URLs

```python title="posts/urls.py"
from buraq.urls import path
from posts import views

urlpatterns = [
    path("/",           views.post_list,   name="post_list"),
    path("/<str:slug>", views.post_detail, name="post_detail"),
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

## 6. Add the app to settings

```python title="config/settings.py"
INSTALLED_APPS = [
    "buraq.contrib.auth",
    "posts",  # add this
]
```

## 7. Create the database tables

```bash
buraq migrate
```

## 8. Run the server

```bash
buraq runserver
```

Visit [http://127.0.0.1:8000/posts/](http://127.0.0.1:8000/posts/) — your blog is live.

Auto-generated API docs: [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs)
