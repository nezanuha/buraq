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
STATIC_URL       = "/static/"
STATIC_ROOT      = str(BASE_DIR / "staticfiles")  # destination for collectstatic
STATICFILES_DIRS = [str(BASE_DIR / "static")]      # source directories

# Storage backend — ManifestStaticFilesStorage adds content-hashed filenames
STATICFILES_STORAGE = "buraq.contrib.staticfiles.storage.StaticFilesStorage"

# MEDIA
MEDIA_DIR = str(BASE_DIR / "media")
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

## Multiple Mailers

```python
# Named email backends — select with send_mail(..., using="transactional")
MAILERS = {
    "transactional": {
        "BACKEND":       "buraq.contrib.email.backends.smtp.SMTPEmailBackend",
        "HOST":          "smtp.sendgrid.net",
        "PORT":          587,
        "HOST_USER":     "apikey",
        "HOST_PASSWORD": "SG.xxx",
        "USE_TLS":       True,
    },
    "bulk": {
        "BACKEND":       "buraq.contrib.email.backends.smtp.SMTPEmailBackend",
        "HOST":          "bulk.mailrelay.com",
        "PORT":          587,
        "HOST_USER":     "bulk@example.com",
        "HOST_PASSWORD": "secret",
        "USE_TLS":       True,
    },
}
```

## Security headers

Configured via `buraq.middleware.SecurityMiddleware`:

```python
# HTTPS redirect
SECURE_SSL_REDIRECT = True   # redirect all HTTP → HTTPS (default: False)

# HSTS
SECURE_HSTS_SECONDS            = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD            = True

# Other headers (all True/set by default)
SECURE_CONTENT_TYPE_NOSNIFF          = True           # X-Content-Type-Options: nosniff
SECURE_REFERRER_POLICY               = "same-origin"  # Referrer-Policy
SECURE_CROSS_ORIGIN_OPENER_POLICY    = "same-origin"  # COOP
X_FRAME_OPTIONS                      = "SAMEORIGIN"   # X-Frame-Options

# Permissions-Policy (empty by default — add what you need)
SECURE_PERMISSIONS_POLICY = {
    "geolocation": "()",
    "microphone":  "()",
    "camera":      "()",
}
```

See [Security Middleware](../topics/security-middleware.md) for setup instructions.

## Template context processors

```python
TEMPLATE_CONTEXT_PROCESSORS = [
    "buraq.template.context_processors.request",   # injects request
    "buraq.template.context_processors.auth",      # injects user
    "buraq.template.context_processors.debug",     # injects DEBUG flag
    "buraq.template.context_processors.i18n",      # injects LANGUAGE_CODE
    "myapp.context_processors.site_settings",      # custom processor
]
```

See [Context Processors](../topics/context-processors.md) for writing custom processors.

## Authentication

```python
SECRET_KEY                 = "your-jwt-secret-key"
JWT_ALGORITHM              = "HS256"
JWT_EXPIRY_MINUTES         = 60

# Custom user model — dotted path to your User model class
# Default: "buraq.contrib.auth.models.User"
AUTH_USER_MODEL            = "myapp.models.MyUser"

# How long (in seconds) password-reset links remain valid
# Default: 259200 (3 days)
PASSWORD_RESET_TIMEOUT     = 259200
```

## Password validators

Control which password-strength rules are enforced on registration and password-change:

```python
AUTH_PASSWORD_VALIDATORS = [
    # Minimum 8 characters (default)
    {"NAME": "buraq.contrib.auth.password_validation.MinimumLengthValidator"},

    # Custom minimum length
    {"NAME": "buraq.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 12}},

    # Reject common passwords (e.g. "password", "123456")
    {"NAME": "buraq.contrib.auth.password_validation.CommonPasswordValidator"},

    # Reject passwords that are entirely numeric
    {"NAME": "buraq.contrib.auth.password_validation.NumericPasswordValidator"},

    # Reject passwords too similar to username / email
    {"NAME": "buraq.contrib.auth.password_validation.UserAttributeSimilarityValidator"},

    # Guard against bcrypt DoS — reject very long passwords
    {"NAME": "buraq.contrib.auth.password_validation.MaximumLengthValidator",
     "OPTIONS": {"max_length": 4096}},
]
```

See [Password Validation](../topics/authentication.md#password-validation) for usage details.

!!! note "Unknown setting names"
    Buraq silently ignores unrecognised setting keys (it does not raise on typos).
    Use an IDE with type hints for `BuraqSettings` to catch misspelled names early.

## Timezone

```python
USE_TZ    = True     # store and return timezone-aware datetimes (default: True)
TIME_ZONE = "UTC"    # default timezone — any IANA name, e.g. "America/New_York"
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
