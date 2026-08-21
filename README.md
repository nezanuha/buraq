# Buraq

**A high-performance, batteries-included Python web framework — built for AI applications, high-traffic APIs, and developers who know Django.**

Buraq delivers Rust-powered performance at every layer — Granian ASGI server, orjson, asyncpg, uv — with a complete full-stack framework: ORM, admin, forms, auth, migrations, templates, signals, cache, and email. All async, all fast.

If you know Django, you already know Buraq. Same views, same URLs, same templates, same ORM patterns — just add `await`. Built on FastAPI and SQLAlchemy 2.0 under the hood, so you get auto-generated API docs, Pydantic validation, and Rust-level performance out of the box.

[![PyPI version](https://img.shields.io/pypi/v/buraq.svg)](https://pypi.org/project/buraq/)
[![Python](https://img.shields.io/pypi/pyversions/buraq.svg)](https://pypi.org/project/buraq/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/nezanuha/buraq/actions/workflows/ci.yml/badge.svg)](https://github.com/nezanuha/buraq/actions/workflows/ci.yml)

---

## Why Buraq?

Modern applications — especially AI backends, LLM APIs, and real-time services — need a framework that handles thousands of concurrent requests without blocking. They also need the full stack: ORM, auth, admin, migrations, cache, and email — not just a router.

At the same time, Python web developers coming from Django shouldn't have to give up familiar patterns just to get async performance. Switching to a low-level async framework means losing everything Django provides out of the box.

Buraq solves both problems. A complete, batteries-included web framework with Rust-powered performance at every layer — and zero re-learning curve for Django developers.

---

## Django Developers: Migrate in Minutes

Buraq is intentionally designed to mirror Django's API. Your existing knowledge transfers directly.

| Django | Buraq |
|---|---|
| `from django.urls import path` | `from buraq.urls import path` |
| `from django.shortcuts import render, redirect` | `from buraq.shortcuts import render, redirect` |
| `from django.views.generic import ListView` | `from buraq.views.generic import ListView` |
| `from django import forms` | `from buraq.forms import ModelForm` |
| `from django.db import models` | `from buraq import models` |
| `from django.contrib.auth.decorators import login_required` | `from buraq.decorators import login_required` |
| `from django.contrib import messages` | `from buraq.contrib.messages import success, error` |
| `python manage.py runserver` | `buraq runserver` |
| `python manage.py makemigrations` | `buraq makemigrations` |
| `python manage.py migrate` | `buraq migrate` |
| `python manage.py startapp` | `buraq startapp` |
| `python manage.py createsuperuser` | `buraq createsuperuser` |
| `python manage.py collectstatic` | `buraq collectstatic` |

The only difference: add `async`/`await` to your views and ORM calls.

```python
# Django
def post_list(request):
    posts = Post.objects.filter(published=True).order_by("-created_at")
    return render(request, "posts/list.html", {"posts": posts})

# Buraq — same pattern, truly async
async def post_list(request):
    posts = await Post.objects.filter(published=True).order_by("-created_at")
    return await render(request, "posts/list.html", {"posts": posts})
```

---

## Quick Start

```bash
pip install buraq
buraq startproject myproject
cd myproject
buraq migrate
buraq runserver
```

Visit `http://127.0.0.1:8000` — your project is running.  
Visit `http://127.0.0.1:8000/api/docs` — Swagger UI, auto-generated.

---

## Everything Included

### ORM & Database
```python
from buraq import models

class Post(models.Model):
    title        = models.CharField(max_length=200)
    slug         = models.SlugField(unique=True)
    content      = models.TextField()
    is_published = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)
    author       = models.ForeignKey("auth.User", on_delete=models.CASCADE)
```

```bash
buraq makemigrations
buraq migrate
```

### URLs
```python
from buraq.urls import path, include

urlpatterns = [
    path("/posts",          views.PostListView.as_view(),   name="post_list"),
    path("/posts/new",      views.PostCreateView.as_view(), name="post_create"),
    path("/posts/<int:pk>", views.PostDetailView.as_view(), name="post_detail"),
    path("/api",            include("myapp.api_urls")),
]
```

### Class-Based Views
```python
from buraq.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

class PostListView(ListView):
    model         = Post
    template_name = "posts/list.html"
    paginate_by   = 10

class PostCreateView(CreateView):
    model         = Post
    form_class    = PostForm
    template_name = "posts/form.html"
    success_url   = "/posts"
```

### Function-Based Views
```python
from buraq.shortcuts import render, redirect, get_object_or_404
from buraq.contrib.messages import success
from buraq.decorators import login_required

@login_required
async def post_create(request):
    form = PostForm(await request.form())
    if form.is_valid():
        await form.save()
        success(request, "Post created successfully.")
        return redirect("/posts")
    return await render(request, "posts/form.html", {"form": form})
```

### Forms & ModelForm
```python
from buraq.forms import ModelForm, CharField, BooleanField

class PostForm(ModelForm):
    class Meta:
        model  = Post
        fields = ["title", "slug", "content", "is_published"]
```

### Templates (Jinja2)
```html
{% extends "base.html" %}

{% block content %}
  {% for post in posts %}
    <h2><a href="/posts/{{ post.id }}">{{ post.title }}</a></h2>
  {% endfor %}

  {% if messages %}
    {% for message in messages %}
      <div class="alert">{{ message }}</div>
    {% endfor %}
  {% endif %}
{% endblock %}
```

### Authentication
```python
from buraq.contrib.auth import authenticate, login, logout
from buraq.decorators import login_required

async def login_view(request):
    user = await authenticate(request, username=username, password=password)
    if user:
        await login(request, user)
        return redirect("/dashboard")
```

### Signals
```python
from buraq.signals import post_save

@post_save.connect(sender=Post)
async def on_post_saved(sender, instance, created, **kwargs):
    if created:
        await notify_subscribers(instance)
```

### Cache
```python
from buraq.contrib.cache import cache

await cache.set("key", value, timeout=300)
value = await cache.get("key")
```

### Email
```python
from buraq.contrib.email import send_mail

await send_mail(
    subject="Welcome to Buraq",
    message="Thanks for signing up.",
    to=["user@example.com"],
)
```

---

## Performance

Buraq is built on the fastest available Python components at every layer:

| Layer            | Library              | Benefit                          |
|------------------|----------------------|----------------------------------|
| ASGI server      | Granian (Rust)       | Rust-based; falls back to uvicorn    |
| Web framework    | FastAPI              | ASGI-native, Pydantic v2         |
| Database driver  | asyncpg              | Fastest async PostgreSQL driver  |
| ORM              | SQLAlchemy 2.0       | Native async, no sync wrapper    |
| JSON             | orjson (Rust)        | 3–10× faster than stdlib json    |
| Password hashing | Argon2id             | PHC winner — memory-hard, fast to verify |
| Package manager  | uv (Rust)            | 10–100× faster than pip          |

---

## Features at a Glance

- **Async ORM** with SQLAlchemy 2.0 — `await Model.objects.filter(...)`
- **Alembic migrations** — `buraq makemigrations` / `buraq migrate`
- **`path()` URL routing** with type-safe converters
- **Class-based views** — ListView, DetailView, CreateView, UpdateView, DeleteView
- **ModelForm** with field validation and `await form.save()`
- **Jinja2 templates** with Django-compatible template tags
- **Built-in auth** — sessions, login/register/logout, password reset
- **Built-in admin panel** — auto-CRUD for every model, `buraq createsuperuser`
- **Flash messages** backed by session storage
- **Signals** — `post_save`, `pre_delete`, custom signals
- **Cache backends** — Redis, Memcached, database, file, in-memory (all async)
- **Email backends** — SMTP, console, file (all async)
- **Static files** — WhiteNoise + `buraq collectstatic`
- **Rate limiting** via SlowAPI
- **Security headers** — HSTS, nosniff, frame options, referrer policy, CSP
- **CORS middleware**
- **orjson** for all JSON responses
- **Granian** ASGI server built-in, falls back to uvicorn
- **Auto API docs** — Swagger UI and ReDoc at `/api/docs`

---

## Documentation

Full documentation: [buraqproject.com](https://buraqproject.com)

- [Installation](https://buraqproject.com/docs/getting-started/installation)
- [Quickstart](https://buraqproject.com/docs/getting-started/quickstart)
- [Migrating from Django](https://buraqproject.com/docs/migrating-from-django)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) — contributions are welcome.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT — see [LICENSE](LICENSE)
