# Buraq

**Buraq** is a high-performance, async-first web framework that brings Django's developer experience to the modern Python async ecosystem — built on [FastAPI](https://fastapi.tiangolo.com/) and [SQLAlchemy 2.0](https://docs.sqlalchemy.org/).

```python
from buraq import Buraq
from buraq.urls import get, post, include
from buraq.shortcuts import render, redirect
from buraq.forms import ModelForm
from buraq import models

app = Buraq(settings_module="config.settings")


class Post(models.Model):
    title   = models.CharField(max_length=200)
    content = models.TextField()
    created = models.DateTimeField(auto_now_add=True)


async def post_list(request):
    posts = await Post.objects.filter(is_published=True).order_by("-created")
    return render(request, "posts/list.html", {"posts": posts})


urlpatterns = [
    get("/posts/", post_list, name="post_list"),
]

app.load_urls(urlpatterns)
```

## Why Buraq?

| Feature | Django | FastAPI | **Buraq** |
|---|---|---|---|
| Django-style ORM | ✅ | ❌ | ✅ |
| Async-first | ❌ | ✅ | ✅ |
| Auto API docs | ❌ | ✅ | ✅ |
| Class-based views | ✅ | ❌ | ✅ |
| Forms & validation | ✅ | ❌ | ✅ |
| Admin panel | ✅ | ❌ | ✅ |
| `manage.py` CLI | ✅ | ❌ | ✅ |
| Type safety | Partial | ✅ | ✅ |

## Key Features

- **Async-first** — every database call, view, and form validation is `async`. No sync wrappers, no `asyncio.run()` hacks.
- **Django-like ORM** — `Model.objects.filter()`, `get_or_404()`, `Q` objects, `F` expressions, signals.
- **ModelForm** — auto-generates forms from model columns, with field-level and cross-field validation.
- **Generic CBVs** — `ListView`, `DetailView`, `CreateView`, `UpdateView`, `DeleteView`.
- **FastAPI underneath** — automatic OpenAPI docs, Pydantic integration, dependency injection.
- **`manage.py` CLI** — `runserver`, `makemigrations`, `migrate`, `startapp`, `startproject`, `createsuperuser`.
- **Built-in auth** — JWT-based authentication, `login_required`, `permission_required`.
- **Cache** — Memory, File, Redis, Memcached backends.
- **Sessions & Messages** — Django-style flash messages backed by the session.

## Requirements

- Python 3.11+
- One async database driver: `aiosqlite`, `asyncpg`, or `aiomysql`

## Installation

```bash
pip install buraq

# with your database driver
pip install buraq aiosqlite        # SQLite
pip install buraq asyncpg          # PostgreSQL
pip install "buraq[mysql]"         # MySQL
```

Or with [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv add buraq aiosqlite
```

## Quickstart

```bash
buraq startproject myblog
cd myblog
uv sync
python manage.py migrate
python manage.py runserver
```

Open [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs) — your API is live.
