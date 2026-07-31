# Project Structure

Running `buraq startproject myblog` creates:

```
myblog/
├── config/
│   ├── __init__.py
│   ├── settings.py       # all project settings
│   └── urls.py           # root URL config + app entry point
├── templates/
│   └── base.html
├── static/
│   ├── css/
│   └── js/
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── main.py               # ASGI entry point (imports app from config/urls.py)
├── manage.py             # CLI — python manage.py <command>
├── alembic.ini
├── pyproject.toml
├── .env
└── .gitignore
```

After running `python manage.py startapp posts`:

```
myblog/
├── posts/
│   ├── __init__.py
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── forms.py
│   ├── admin.py
│   ├── schemas.py        # Pydantic schemas for API endpoints
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
from buraq import Buraq
from buraq.urls import path, include

app = Buraq(settings_module="config.settings")

urlpatterns = [
    path("/auth",  include("buraq.contrib.auth.urls")),
    path("/posts", include("posts.urls")),
]

app.load_urls(urlpatterns)
```

### `manage.py`

Works exactly like Django's `manage.py`. Auto-detects `.venv` so you don't need to activate it:

```bash
python manage.py runserver
python manage.py runserver 8080       # custom port
python manage.py makemigrations
python manage.py migrate
python manage.py startapp <name>
python manage.py createsuperuser
```

### `alembic/`

Buraq uses [Alembic](https://alembic.sqlalchemy.org/) for database migrations — the same tool SQLAlchemy recommends. `makemigrations` and `migrate` are thin wrappers over Alembic commands.
