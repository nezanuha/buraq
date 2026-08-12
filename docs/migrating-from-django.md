# Migrating from Django

Buraq is intentionally designed to mirror Django's patterns. If you know Django, most of what you know transfers directly — the main difference is adding `async`/`await` to your views and ORM calls.

## Installation

=== "Django"

    ```bash
    pip install django
    django-admin startproject myproject
    cd myproject
    python manage.py migrate
    python manage.py runserver
    ```

=== "Buraq"

    ```bash
    pip install buraq
    buraq startproject myproject
    cd myproject
    buraq migrate
    buraq runserver
    ```

---

## Management Commands

| Django | Buraq |
|---|---|
| `python manage.py runserver` | `buraq runserver` |
| `python manage.py makemigrations` | `buraq makemigrations` |
| `python manage.py migrate` | `buraq migrate` |
| `python manage.py startapp name` | `buraq startapp name` |
| `python manage.py startproject name` | `buraq startproject name` |
| `python manage.py createsuperuser` | `buraq createsuperuser` |
| `python manage.py collectstatic` | `buraq collectstatic` |
| `python manage.py findstatic file` | `buraq findstatic file` |
| `python manage.py shell` | `buraq shell` |
| `python manage.py check` | `buraq check` |
| `python manage.py check --deploy` | `buraq check --deploy` |
| `python manage.py dbshell` | `buraq dbshell` |
| `python manage.py dumpdata` | `buraq dumpdata` |
| `python manage.py loaddata fixture` | `buraq loaddata fixture` |
| `python manage.py flush` | `buraq flush` |
| `python manage.py changepassword` | `buraq changepassword` |
| `python manage.py inspectdb` | `buraq inspectdb` |
| `python manage.py diffsettings` | `buraq diffsettings` |
| `python manage.py sendtestemail` | `buraq sendtestemail` |
| `python manage.py makemessages -l ar` | `buraq makemessages -l ar` |
| `python manage.py compilemessages` | `buraq compilemessages` |
| `python manage.py sqlmigrate abc123` | `buraq sqlmigrate abc123` |
| `python manage.py squashmigrations` | `buraq squashmigrations` |
| `python manage.py optimizemigration` | `buraq optimizemigration` |
| `python manage.py sqlflush` | `buraq sqlflush` |
| `python manage.py sqlsequencereset` | `buraq sqlsequencereset` |
| `python manage.py testserver fixtures/` | `buraq testserver fixtures/` |
| `python manage.py test` | `buraq test` |
| `python manage.py showmigrations` | `buraq showmigrations` |
| `python manage.py clearsessions` | `buraq clearsessions` |
| `python manage.py createcachetable` | `buraq createcachetable` |
| `python manage.py remove_stale_contenttypes` | `buraq remove_stale_contenttypes` |
| `python manage.py version` | `buraq version` |
| `python manage.py worker` | `buraq worker` |
| `django-admin` | `buraq` (same CLI, no separate admin tool) |

---

## Imports

| Django | Buraq |
|---|---|
| `from django.urls import path, include` | `from buraq.urls import path, include` |
| `from django.shortcuts import render, redirect` | `from buraq.shortcuts import render, redirect` |
| `from django.shortcuts import get_object_or_404` | `from buraq.shortcuts import get_object_or_404` |
| `from django.shortcuts import get_list_or_404` | `from buraq.shortcuts import get_list_or_404` |
| `from django.urls import reverse_lazy` | `from buraq.urls import reverse_lazy` |
| `from django.db import models` | `from buraq import models` |
| `from django.views.generic import ListView` | `from buraq.views.generic import ListView` |
| `from django.views.generic import DetailView` | `from buraq.views.generic import DetailView` |
| `from django.views.generic import CreateView` | `from buraq.views.generic import CreateView` |
| `from django.views.generic import UpdateView` | `from buraq.views.generic import UpdateView` |
| `from django.views.generic import DeleteView` | `from buraq.views.generic import DeleteView` |
| `from django import forms` | `from buraq.forms import ModelForm` |
| `from django.contrib.auth.decorators import login_required` | `from buraq.decorators import login_required` |
| `from django.contrib import messages` | `from buraq.contrib.messages import success, error, info` |

---

## Models

=== "Django"

    ```python
    from django.db import models

    class Post(models.Model):
        title        = models.CharField(max_length=200)
        slug         = models.SlugField(unique=True)
        content      = models.TextField()
        is_published = models.BooleanField(default=False)
        created_at   = models.DateTimeField(auto_now_add=True)
        author       = models.ForeignKey("auth.User", on_delete=models.CASCADE)

        class Meta:
            ordering = ["-created_at"]
    ```

=== "Buraq"

    ```python
    from buraq import models

    class Post(models.Model):
        title        = models.CharField(max_length=200)
        slug         = models.SlugField(unique=True)
        content      = models.TextField()
        is_published = models.BooleanField(default=False)
        created_at   = models.DateTimeField(auto_now_add=True)
        author       = models.ForeignKey("auth.User", on_delete=models.CASCADE)

        class Meta:
            ordering = ["-created_at"]
    ```

---

## ORM Queries

| Django | Buraq |
|---|---|
| `Post.objects.all()` | `await Post.objects.all()` |
| `Post.objects.filter(published=True)` | `await Post.objects.filter(published=True)` |
| `Post.objects.get(pk=pk)` | `await Post.objects.get(pk=pk)` |
| `Post.objects.create(title="Hello")` | `await Post.objects.create(title="Hello")` |
| `post.save()` | `await post.save()` |
| `post.delete()` | `await post.delete()` |
| `Post.objects.order_by("-created_at")` | `await Post.objects.order_by("-created_at")` |
| `Post.objects.filter(...).count()` | `await Post.objects.filter(...).count()` |
| `Post.objects.select_related("author")` | `await Post.objects.select_related("author")` |

The only difference: every ORM call needs `await`.

---

## URLs

=== "Django"

    ```python
    from django.urls import path, include
    from posts import views

    urlpatterns = [
        path("posts/",            views.PostListView.as_view(),   name="post_list"),
        path("posts/new/",        views.PostCreateView.as_view(), name="post_create"),
        path("posts/<int:pk>/",   views.PostDetailView.as_view(), name="post_detail"),
        path("api/",              include("myapp.api_urls")),
    ]
    ```

=== "Buraq"

    ```python
    from buraq.urls import path, include
    from posts import views

    urlpatterns = [
        path("/posts",            views.PostListView.as_view(),   name="post_list"),
        path("/posts/new",        views.PostCreateView.as_view(), name="post_create"),
        path("/posts/<int:pk>",   views.PostDetailView.as_view(), name="post_detail"),
        path("/api",              include("myapp.api_urls")),
    ]
    ```

---

## Views

### Function-Based Views

=== "Django"

    ```python
    from django.shortcuts import render, redirect, get_object_or_404
    from django.contrib.auth.decorators import login_required
    from django.contrib import messages

    @login_required
    def post_create(request):
        form = PostForm(request.POST or None)
        if form.is_valid():
            form.save()
            messages.success(request, "Post created.")
            return redirect("/posts")
        return render(request, "posts/form.html", {"form": form})
    ```

=== "Buraq"

    ```python
    from buraq.shortcuts import render, redirect, get_object_or_404
    from buraq.decorators import login_required
    from buraq.contrib.messages import success

    @login_required
    async def post_create(request):
        form = PostForm(await request.form())
        if form.is_valid():
            await form.save()
            success(request, "Post created.")
            return redirect("/posts")
        return render(request, "posts/form.html", {"form": form})
    ```

### Class-Based Views

=== "Django"

    ```python
    from django.views.generic import ListView, CreateView

    class PostListView(ListView):
        model         = Post
        template_name = "posts/list.html"
        paginate_by   = 10

    class PostCreateView(CreateView):
        model         = Post
        form_class    = PostForm
        template_name = "posts/form.html"
        success_url   = "/posts/"
    ```

=== "Buraq"

    ```python
    from buraq.views.generic import ListView, CreateView

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

---

## Forms

=== "Django"

    ```python
    from django import forms

    class PostForm(forms.ModelForm):
        class Meta:
            model  = Post
            fields = ["title", "slug", "content", "is_published"]
    ```

=== "Buraq"

    ```python
    from buraq.forms import ModelForm

    class PostForm(ModelForm):
        class Meta:
            model  = Post
            fields = ["title", "slug", "content", "is_published"]
    ```

---

## Templates

Buraq uses Jinja2 instead of Django's template engine. The syntax is nearly identical.

| Django template | Jinja2 (Buraq) |
|---|---|
| `{% extends "base.html" %}` | `{% extends "base.html" %}` |
| `{% block content %}` | `{% block content %}` |
| `{% for item in items %}` | `{% for item in items %}` |
| `{% if condition %}` | `{% if condition %}` |
| `{% url 'post_list' %}` | `{{ url('post_list') }}` |
| `{{ variable }}` | `{{ variable }}` |
| `{% include "partial.html" %}` | `{% include "partial.html" %}` |
| `{{ variable\|upper }}` | `{{ variable\|upper }}` |

---

## Static Files

### Settings

| Django | Buraq |
|---|---|
| `STATIC_URL = "/static/"` | `STATIC_URL = "/static/"` |
| `STATIC_ROOT = str(BASE_DIR / "staticfiles")` | `STATIC_ROOT = str(BASE_DIR / "staticfiles")` |
| `STATICFILES_DIRS = [str(BASE_DIR / "static")]` | `STATICFILES_DIRS = [str(BASE_DIR / "static")]` |
| `STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"` | `STATICFILES_STORAGE = "buraq.contrib.staticfiles.storage.ManifestStaticFilesStorage"` |
| `STATICFILES_FINDERS = [...]` | `STATICFILES_FINDERS = [...]` |
| `MEDIA_ROOT = str(BASE_DIR / "media")` | `MEDIA_DIR = str(BASE_DIR / "media")` |
| `MEDIA_URL = "/media/"` | `MEDIA_URL = "/media/"` |

### Template tags

Django requires `{% load static %}` before using `{% static %}`. Buraq registers the tag automatically — no load needed:

=== "Django"

    ```html+django
    {% load static %}
    <link rel="stylesheet" href="{% static 'css/style.css' %}">
    <img src="{% static 'images/logo.png' %}">
    ```

=== "Buraq (Django-style tag)"

    ```html+jinja
    {# No {% load %} needed #}
    <link rel="stylesheet" href="{% static 'css/style.css' %}">
    <img src="{% static 'images/logo.png' %}">
    ```

=== "Buraq (function-call style)"

    ```html+jinja
    <link rel="stylesheet" href="{{ static('css/style.css') }}">
    <img src="{{ static('images/logo.png') }}">
    ```

### Finders

| Django | Buraq |
|---|---|
| `django.contrib.staticfiles.finders.FileSystemFinder` | `buraq.contrib.staticfiles.finders.FileSystemFinder` |
| `django.contrib.staticfiles.finders.AppDirectoriesFinder` | `buraq.contrib.staticfiles.finders.AppDirectoriesFinder` |

### Storage backends

| Django | Buraq |
|---|---|
| `django.contrib.staticfiles.storage.StaticFilesStorage` | `buraq.contrib.staticfiles.storage.StaticFilesStorage` |
| `django.contrib.staticfiles.storage.ManifestStaticFilesStorage` | `buraq.contrib.staticfiles.storage.ManifestStaticFilesStorage` |

---

## Flash Messages

=== "Django"

    ```python
    from django.contrib import messages

    messages.success(request, "Saved successfully.")
    messages.error(request, "Something went wrong.")
    messages.info(request, "Please verify your email.")
    ```

=== "Buraq"

    ```python
    from buraq.contrib.messages import success, error, info

    success(request, "Saved successfully.")
    error(request, "Something went wrong.")
    info(request, "Please verify your email.")
    ```

Template usage is identical in both:

```html
{% for message in messages %}
  <div class="alert alert-{{ message.tags }}">{{ message }}</div>
{% endfor %}
```

---

## Authentication

=== "Django"

    ```python
    from django.contrib.auth import authenticate, login, logout
    from django.contrib.auth.decorators import login_required

    def login_view(request):
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("/dashboard")
    ```

=== "Buraq"

    ```python
    from buraq.contrib.auth import authenticate, login, logout
    from buraq.decorators import login_required

    async def login_view(request):
        user = await authenticate(request, username=username, password=password)
        if user:
            await login(request, user)
            return redirect("/dashboard")
    ```

---

## Settings

Most settings follow the same naming convention. Key differences:

| Django `settings.py` | Buraq `settings.py` |
|---|---|
| `DATABASES = {"default": {...}}` | `DATABASE_URL = "postgresql+asyncpg://..."` |
| `INSTALLED_APPS` | `INSTALLED_APPS` |
| `MIDDLEWARE` | `MIDDLEWARE` |
| `TEMPLATES` | `TEMPLATES` |
| `STATIC_URL` | `STATIC_URL` |
| `MEDIA_URL` | `MEDIA_URL` |
| `SECRET_KEY` | `SECRET_KEY` |
| `DEBUG` | `DEBUG` |
| `ALLOWED_HOSTS` | `ALLOWED_HOSTS` |

---

## Background Tasks

| Django | Buraq |
|---|---|
| `from django.tasks import background_task` | `from buraq.contrib.tasks import background_task` |
| `@background_task` | `@background_task` |
| `@background_task(queue="q", priority=5)` | `@background_task(queue="q", priority=5)` |
| `await task.aenqueue(...)` | `await task.aenqueue(...)` |
| `BaseTaskBackend` | `buraq.contrib.tasks.backends.base.BaseTaskBackend` |
| `TaskResult.arefresh()` | `result.arefresh()` |
| `TASKS = {"default": {"BACKEND": "..."}}` | `TASKS = {"default": {"BACKEND": "..."}}` |

Both frameworks use an identical API. The only difference is the import path.

---

## Content Security Policy

| Django | Buraq |
|---|---|
| `django.middleware.csp.ContentSecurityPolicyMiddleware` | `buraq.middleware.csp.ContentSecurityPolicyMiddleware` |
| `CONTENT_SECURITY_POLICY = {...}` | `CONTENT_SECURITY_POLICY = {...}` |
| `CONTENT_SECURITY_POLICY_REPORT_ONLY = {...}` | `CONTENT_SECURITY_POLICY_REPORT_ONLY = {...}` |
| `CONTENT_SECURITY_POLICY_NONCE_DIRECTIVES` | `CONTENT_SECURITY_POLICY_NONCE_DIRECTIVES` |
| `from django.views.decorators.csp import csp_override` | `from buraq.views.decorators.csp import csp_override` |
| `from django.views.decorators.csp import csp_report_only_override` | `from buraq.views.decorators.csp import csp_report_only_override` |
| `from django.utils.csp import CSP` | `from buraq.utils.csp import CSP` |

---

## Authentication Backends

| Django | Buraq |
|---|---|
| `django.contrib.auth.backends.ModelBackend` | `buraq.contrib.auth.backends.ModelBackend` |
| `django.contrib.auth.backends.AllowAllUsersModelBackend` | `buraq.contrib.auth.backends.AllowAllUsersModelBackend` |
| `django.contrib.auth.backends.AllowAllUsersRemoteUserBackend` | `buraq.contrib.auth.backends.AllowAllUsersRemoteUserBackend` |

---

## Model Fields

| Django | Buraq |
|---|---|
| `models.GeneratedField(expression=..., output_field=..., db_persist=True)` | `models.GeneratedField(expression=..., output_field=..., db_persist=True)` |
| `models.CompositePrimaryKey("field1", "field2")` in `Meta.primary_key` | `models.CompositePrimaryKey("field1", "field2")` in `Meta.primary_key` |

---

## Aggregates

| Django | Buraq |
|---|---|
| `from django.db.models import AnyValue` | `from buraq.orm.aggregates import AnyValue` |

---

## Test Utilities

| Django | Buraq |
|---|---|
| `from django.test import TestCase` | `from buraq.test import TestCase` |
| `self.captureOnCommitCallbacks()` | `captureOnCommitCallbacks()` context manager from `buraq.test` |
| `MessagesTestMixin` + `assertMessages()` | `from buraq.test import MessagesTestMixin` |
| `InMemoryStorage` | `from buraq.contrib.staticfiles.storage import InMemoryStorage` |

---

## Cryptographic Signing

Both frameworks sign data the same way — HMAC-SHA256 keyed with `SECRET_KEY`:

| Django | Buraq |
|---|---|
| `from django.core import signing` | `from buraq.utils import signing` |
| `signing.dumps(obj)` | `signing.dumps(obj)` |
| `signing.loads(token, max_age=3600)` | `signing.loads(token, max_age=3600)` |
| `signing.Signer()` | `signing.Signer()` |
| `signing.TimestampSigner()` | `signing.TimestampSigner()` |
| `BadSignature` | `signing.BadSignature` |
| `SignatureExpired` | `signing.SignatureExpired` |

The API is identical — only the import path differs.

---

## What's Different

- **Every ORM call needs `await`** — this is the biggest change
- **Views must be `async def`** — synchronous views are not supported
- **Database URL** replaces Django's `DATABASES` dict
- **Jinja2** instead of Django's template engine — syntax is ~95% compatible
- **JWT auth** is built-in alongside session auth
- **No `syncdb`** — Alembic handles all migrations via `buraq makemigrations`
- **`buraq` CLI** replaces `python manage.py`
