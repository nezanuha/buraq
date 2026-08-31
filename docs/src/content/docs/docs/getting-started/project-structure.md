---
title: "Project Structure"
description: "All configuration lives here — database, installed apps, middleware, cache, email, etc. See Settings for the full reference."
---

Running `buraq startproject myblog` creates:

```
myblog/
├── config/
│   ├── __init__.py
│   ├── settings.py       # all project settings
│   └── urls.py           # root URL config — urlpatterns and nothing else
├── templates/
│   └── base.html
├── static/
│   ├── css/
│   └── js/
├── main.py               # ASGI entry point — builds the application
├── manage.py             # CLI — buraq <command>
├── pyproject.toml
├── .env
└── .gitignore
```

After running `buraq startapp posts`:

```
myblog/
├── posts/
│   ├── __init__.py
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── forms.py
│   ├── admin.py
│   ├── schemas.py        # Pydantic schemas for JSON endpoints — see Schemas
│   └── migrations/
│       └── __init__.py
...
```

## Key files

### `config/settings.py`

All configuration lives here — database, installed apps, middleware, cache, email, etc.
See [Settings](settings.md) for the full reference.

### `config/urls.py`

The root URL configuration. Creates the `app` instance and loads all URL patterns.

```python
from buraq.urls import path, include

urlpatterns = [
    path("/auth",  include("buraq.contrib.auth.urls")),
    path("/posts", include("posts.urls")),
]
```

### `manage.py`

Works exactly like Django's `manage.py`. Auto-detects `.venv` so you don't need to activate it:

```bash
buraq runserver
buraq runserver 8080       # custom port
buraq makemigrations
buraq migrate
buraq startapp <name>
buraq createsuperuser
```

### `alembic/`

Buraq uses [Alembic](https://alembic.sqlalchemy.org/) for database migrations — the same tool SQLAlchemy recommends. `makemigrations` and `migrate` are thin wrappers over Alembic commands.
