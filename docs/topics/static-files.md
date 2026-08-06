# Static Files

## Configuration

```python title="config/settings.py"
STATIC_DIR  = str(BASE_DIR / "static")   # where your static files live
STATIC_URL  = "/static/"                  # URL prefix
STATIC_ROOT = str(BASE_DIR / "staticfiles")  # destination for collectstatic
```

## In templates

```html+jinja
<link rel="stylesheet" href="{{ url_for('static', path='/css/style.css') }}">
<script src="{{ url_for('static', path='/js/app.js') }}"></script>
<img src="{{ url_for('static', path='/images/logo.png') }}">
```

## Collecting for production

```bash
buraq collectstatic
```

Copies all static files into `STATIC_ROOT`. Serve that directory with Nginx or WhiteNoise in production.

## WhiteNoise (production)

```bash
uv add "buraq[production]"   # installs whitenoise
```

```python title="config/urls.py"
from whitenoise import WhiteNoise

app.mount("/static", WhiteNoise(directory=settings.STATIC_ROOT))
```

## Media files

For user-uploaded files:

```python title="config/settings.py"
MEDIA_DIR = str(BASE_DIR / "media")
MEDIA_URL = "/media/"
```

Media files are served automatically at `MEDIA_URL` when `MEDIA_DIR` exists.
