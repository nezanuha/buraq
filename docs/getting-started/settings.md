# Settings

All settings live in `config/settings.py`. Buraq reads them at startup via the `settings_module` argument passed to `Buraq(settings_module="config.settings")`.

## Core settings

```python title="config/settings.py"
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY
SECRET_KEY   = "change-me-in-production"
DEBUG        = True
ALLOWED_HOSTS = ["*"]

# APPS
INSTALLED_APPS = [
    "buraq.contrib.auth",
    "posts",
]

# DATABASE
DATABASE_URL = "sqlite+aiosqlite:///./db.sqlite3"

# TEMPLATES
TEMPLATES_DIR = str(BASE_DIR / "templates")

# STATIC FILES
STATIC_DIR  = str(BASE_DIR / "static")
STATIC_URL  = "/static/"
STATIC_ROOT = str(BASE_DIR / "staticfiles")   # for collectstatic

# MEDIA
MEDIA_DIR = ""
MEDIA_URL = "/media/"
```

## Database

```python
# SQLite (development)
DATABASE_URL = "sqlite+aiosqlite:///./db.sqlite3"

# PostgreSQL (production)
DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/mydb"

# MySQL
DATABASE_URL = "mysql+aiomysql://user:password@localhost:3306/mydb"
```

## Cache

```python
# In-memory (default, single-process only)
CACHE_BACKEND = "buraq.contrib.cache.backends.memory.MemoryCacheBackend"

# Redis (recommended for production)
CACHE_BACKEND   = "buraq.contrib.cache.backends.redis.RedisCacheBackend"
CACHE_REDIS_URL = "redis://localhost:6379/0"

# Memcached
CACHE_BACKEND        = "buraq.contrib.cache.backends.memcached.MemcachedCacheBackend"
CACHE_MEMCACHED_URL  = "memcached://localhost:11211"

# File
CACHE_BACKEND   = "buraq.contrib.cache.backends.file.FileCacheBackend"
CACHE_FILE_PATH = "/tmp/buraq_cache"

# Shared options
CACHE_KEY_PREFIX      = "myapp:"
CACHE_DEFAULT_TIMEOUT = 300   # seconds
```

## Email

```python
EMAIL_BACKEND      = "buraq.contrib.email.backends.smtp.SMTPEmailBackend"
EMAIL_HOST         = "smtp.gmail.com"
EMAIL_PORT         = 587
EMAIL_USE_TLS      = True
EMAIL_HOST_USER    = "you@gmail.com"
EMAIL_HOST_PASSWORD = "your-app-password"
DEFAULT_FROM_EMAIL  = "you@gmail.com"

# During development — write emails to disk instead of sending
EMAIL_BACKEND   = "buraq.contrib.email.backends.file.FileEmailBackend"
EMAIL_FILE_PATH = "./sent_emails"
```

## Authentication

```python
SECRET_KEY          = "your-jwt-secret-key"
JWT_ALGORITHM       = "HS256"
JWT_EXPIRY_MINUTES  = 60
```

## Sessions

```python
SESSION_COOKIE_NAME     = "buraq_session"
SESSION_COOKIE_MAX_AGE  = 1209600   # 2 weeks in seconds
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "lax"
```

## CORS

```python
CORS_ALLOW_ORIGINS      = ["https://myfrontend.com"]
CORS_ALLOW_CREDENTIALS  = True
CORS_ALLOW_METHODS      = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS      = ["*"]
```

## Full defaults reference

All settings have defaults. You only need to specify what you want to override.
See `buraq/conf/defaults.py` for the complete list.

!!! warning "SECRET_KEY in production"
    Always set a strong, random `SECRET_KEY` in production and never commit it to version control. Use environment variables:

    ```python
    import os
    SECRET_KEY = os.environ["SECRET_KEY"]
    ```
