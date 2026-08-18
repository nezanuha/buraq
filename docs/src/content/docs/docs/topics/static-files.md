---
title: "Static Files"
description: "Both forms return the same URL. When ManifestStaticFilesStorage is active, both automatically return the hashed URL (e.g. /static/css/style.abc123de.css)."
---

## Configuration

```python title="config/settings.py"
STATIC_URL  = "/static/"                     # URL prefix (trailing slash required)
STATIC_ROOT = str(BASE_DIR / "staticfiles")  # destination for collectstatic

# One or more source directories (in priority order)
STATICFILES_DIRS = [
    str(BASE_DIR / "static"),          # project-level static files
    str(BASE_DIR / "theme" / "static"), # shared component library, etc.
]

# Storage backend (default: local filesystem, no hashing)
STATICFILES_STORAGE = "buraq.contrib.staticfiles.storage.StaticFilesStorage"

# Finder classes — controls where collectstatic looks for files
STATICFILES_FINDERS = [
    "buraq.contrib.staticfiles.finders.FileSystemFinder",    # searches STATICFILES_DIRS
    "buraq.contrib.staticfiles.finders.AppDirectoriesFinder", # searches each app's static/
]
```

## In templates

Two equivalent styles — use whichever you prefer:

**Function call (Jinja2 native):**

```html+jinja
<link rel="stylesheet" href="{{ static('css/style.css') }}">
<script src="{{ static('js/app.js') }}"></script>
<img src="{{ static('images/logo.png') }}">
<img src="{{ media('uploads/photo.jpg') }}">
```

**Block tag (Django-style) — no `{% load %}` needed:**

```html+jinja
<link rel="stylesheet" href="{% static 'css/style.css' %}">
<script src="{% static 'js/app.js' %}"></script>
<img src="{% static 'images/logo.png' %}">
<img src="{% media 'uploads/photo.jpg' %}">
```

Both forms return the same URL. When `ManifestStaticFilesStorage` is active, both automatically return the hashed URL (e.g. `/static/css/style.abc123de.css`).

The `STATIC_URL` and `MEDIA_URL` prefixes are also available as template variables:

```html+jinja
<img src="{{ STATIC_URL }}images/logo.png">
<img src="{{ MEDIA_URL }}uploads/photo.jpg">
```

## Collecting for production

```bash
buraq collectstatic
```

Discovers files via all configured finders and copies them into `STATIC_ROOT`:

```
Collecting static files into /app/staticfiles ...
Done. Copied: 24, Skipped (unchanged): 8, Post-processed: 24
```

Pass `--clear` to wipe `STATIC_ROOT` before collecting:

```bash
buraq collectstatic --clear
```

## Production serving with WhiteNoise

Install WhiteNoise:

```bash
uv add whitenoise
```

That's it. When `DEBUG=False`, Buraq automatically mounts WhiteNoise instead of the development file server. WhiteNoise compresses all files (gzip + brotli) once at startup, serves from memory, and sets far-future `Cache-Control` headers — no Nginx layer needed.

Set `STATIC_ROOT` to the directory WhiteNoise should serve from (after `collectstatic`):

```python title="config/settings.py"
STATIC_ROOT = str(BASE_DIR / "staticfiles")
```

If WhiteNoise is not installed, Buraq logs a warning and falls back to the development file server.

## Hashed filenames (cache-busting)

Switch to `ManifestStaticFilesStorage` to get content-hashed filenames:

```python title="config/settings.py"
STATICFILES_STORAGE = "buraq.contrib.staticfiles.storage.ManifestStaticFilesStorage"
```

After `buraq collectstatic`, each file is renamed to include an MD5 hash of its content:

```
css/style.css  →  css/style.abc123de.css
js/app.js      →  js/app.9f4b21cc.js
```

A manifest file (`staticfiles.json`) maps original names to hashed names. The `static()` template function and `{% static %}` tag look up the hashed URL automatically — no template changes needed:

```html+jinja
{% static 'css/style.css' %}
{# renders: /static/css/style.abc123de.css #}
```

Because the filename changes when the content changes, browsers always load the new version after a deploy — even with `Cache-Control: max-age=31536000, immutable`.

**Workflow:**

```bash
# After every deploy:
buraq collectstatic --clear
# Restart the app — WhiteNoise picks up the new hashed files on startup
```

## App-level static files

Each app in `INSTALLED_APPS` can ship its own static files in a `static/` subdirectory:

```
posts/
  static/
    posts/
      style.css
      logo.png
```

`AppDirectoriesFinder` (enabled by default) discovers these automatically. `buraq collectstatic` copies them alongside project-level files into `STATIC_ROOT`.

Namespace your files under the app name (e.g. `posts/style.css`) to avoid collisions between apps.

## Custom finders

Implement a finder class with `find(path)` and `list()` methods, then add it to `STATICFILES_FINDERS`:

```python title="myapp/finders.py"
class NodeModulesFinder:
    def find(self, path):
        full = Path("node_modules") / path
        return str(full) if full.is_file() else None

    def list(self):
        for f in Path("node_modules").rglob("*"):
            if f.is_file():
                yield str(f.relative_to("node_modules")), str(f)
```

```python title="config/settings.py"
STATICFILES_FINDERS = [
    "buraq.contrib.staticfiles.finders.FileSystemFinder",
    "buraq.contrib.staticfiles.finders.AppDirectoriesFinder",
    "myapp.finders.NodeModulesFinder",
]
```

## Cache-Control headers (optional middleware)

`CacheControlMiddleware` sets `Cache-Control` headers on static file responses:

- `DEBUG=True` → `Cache-Control: no-cache`
- `DEBUG=False` → `Cache-Control: public, max-age=31536000, immutable`

```python title="config/settings.py"
MIDDLEWARE = [
    ...
    "buraq.contrib.staticfiles.middleware.CacheControlMiddleware",
]
```

## Media files

For user-uploaded files:

```python title="config/settings.py"
MEDIA_DIR = str(BASE_DIR / "media")
MEDIA_URL = "/media/"
```

Buraq auto-mounts `MEDIA_DIR` at `MEDIA_URL` when the directory exists. Use `{{ media('path') }}` or `{% media 'path' %}` in templates.

## Storage API helpers

`get_storage()` returns the singleton storage backend instance (configured by `STATICFILES_STORAGE`). `reset_storage()` clears the singleton so the next call to `get_storage()` creates a fresh instance — useful in tests that swap storage backends via `override_settings`:

```python
from buraq.contrib.staticfiles.storage import get_storage, reset_storage

storage = get_storage()
url = storage.url("css/style.css")

# In tests — after override_settings changes STATICFILES_STORAGE:
reset_storage()
storage = get_storage()   # picks up the new backend
```

## InMemoryStorage (testing)

`InMemoryStorage` stores files as bytes in a plain dict — no disk I/O, no cleanup needed. It is designed for tests that need to exercise file upload or storage logic without touching the filesystem.

```python
from buraq.contrib.staticfiles.storage import InMemoryStorage

storage = InMemoryStorage(base_url="/static/")

# Save from bytes
storage.save("logo.png", b"\x89PNG...")

# Save from a file path
storage.save("style.css", "/path/to/style.css")

# Read back
with storage.open("logo.png") as f:
    data = f.read()

storage.exists("logo.png")   # True
storage.size("logo.png")     # int
storage.url("logo.png")      # "/static/logo.png"
storage.delete("logo.png")
storage.clear()              # remove all files
```

Use globally via settings to redirect all static file operations in a test suite:

```python
# tests/conftest.py
from buraq.test import override_settings

@pytest.fixture(autouse=True)
def in_memory_static():
    with override_settings(
        STATICFILES_STORAGE="buraq.contrib.staticfiles.storage.InMemoryStorage"
    ):
        yield
```

## How it works internally

| `DEBUG` | Static backend | Media backend |
|---|---|---|
| `True` | FastAPI `StaticFiles` (reads from disk) | FastAPI `StaticFiles` |
| `False` + whitenoise installed | WhiteNoise (memory, compressed) | FastAPI `StaticFiles` |
| `False` + whitenoise missing | FastAPI `StaticFiles` + warning logged | FastAPI `StaticFiles` |
