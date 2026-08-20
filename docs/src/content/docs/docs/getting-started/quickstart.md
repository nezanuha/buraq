---
title: "Quickstart"
description: "Build a working blog with models, views, URLs and templates."
---

A working blog in about five minutes — models, views, URLs, templates.

New here? [Installation](/docs/getting-started/installation) covers getting the
`buraq` command first.

## 1. Create the project

```bash
buraq startproject myblog
cd myblog
```

That writes the project and installs its dependencies.

## 2. Create the app

```bash
buraq startapp posts
```

## 3. Define the model

```python title="posts/models.py"
from buraq import models


class Post(models.Model):
    title        = models.CharField(max_length=200)
    slug         = models.SlugField(max_length=200, unique=True)
    content      = models.TextField()
    is_published = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)
```

## 4. Write the views

Every view is `async`, and so is `render`:

```python title="posts/views.py"
from buraq.shortcuts import get_object_or_404, render
from posts.models import Post


async def post_list(request):
    posts = await Post.objects.filter(is_published=True).order_by("-created_at")
    return await render(request, "posts/list.html", {"posts": posts})


async def post_detail(request, slug: str):
    post = await get_object_or_404(Post, slug=slug)
    return await render(request, "posts/detail.html", {"post": post})
```

## 5. Add the templates

Templates live under the project's `templates/` directory, in a folder matching
the paths the views asked for:

```html title="templates/posts/list.html"
<h1>Posts</h1>

<ul>
  {% for post in posts %}
    <li><a href="/posts/{{ post.slug }}">{{ post.title }}</a></li>
  {% else %}
    <li>Nothing published yet.</li>
  {% endfor %}
</ul>
```

```html title="templates/posts/detail.html"
<h1>{{ post.title }}</h1>

<p>{{ post.content }}</p>

<a href="/posts/">Back to all posts</a>
```

## 6. Wire up the URLs

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
from buraq.urls import include, path

app = Buraq(settings_module="config.settings")

urlpatterns = [
    path("/posts", include("posts.urls")),
]

app.load_urls(urlpatterns)
```

## 7. Install the app

```python title="config/settings.py"
INSTALLED_APPS = [
    "buraq.contrib.auth",
    "posts",  # add this
]
```

## 8. Create the tables

```bash
buraq migrate                     # apply the migrations Buraq ships
buraq makemigrations "add posts"  # generate one for your model
buraq migrate                     # apply it
```

Three commands on a new project, two from then on. Autogeneration compares your
models against the database and will not run while the database is behind, and a
new project starts behind — `buraq.contrib.auth` ships migrations of its own.
The first `migrate` clears that, and afterwards it is the usual `makemigrations`
then `migrate`.

## 9. Run it

```bash
buraq runserver
```

[http://127.0.0.1:8000/posts/](http://127.0.0.1:8000/posts/) — empty until you
add a post, which the [admin](/docs/topics/admin) or
[`buraq shell`](/docs/management/commands) can do:

```bash
buraq shell -c "await Post.objects.create(title='Hello', slug='hello', content='First post.', is_published=True)"
```

Auto-generated API docs are at
[/api/docs](http://127.0.0.1:8000/api/docs).

## Where to go next

- [Models](/docs/topics/orm/models) — fields, relationships, `Meta` options
- [Views](/docs/topics/views/) — function and class-based
- [Templates](/docs/topics/templates) — inheritance, tags, filters
- [Admin](/docs/topics/admin) — a working admin for your models
