
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: The placeholder SECRET_KEY a project ships with until it sets its own.
#: Shared with the security checks so the two cannot drift apart.
INSECURE_SECRET_KEY = "change-me-in-production"


class BuraqSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core
    DEBUG: bool = False
    SECRET_KEY: str = INSECURE_SECRET_KEY
    ALLOWED_HOSTS: list[str] = ["*"]

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def _accept_comma_separated_hosts(cls, value):
        """
        Read "a,b" as well as JSON.

        A list field in .env is parsed as JSON, while a project's settings module
        reads the same variable from the environment and splits on commas. One
        variable with two incompatible spellings meant whichever you picked broke
        the other reader.
        """
        if isinstance(value, str) and not value.strip().startswith("["):
            return [host.strip() for host in value.split(",") if host.strip()]
        return value
    INSTALLED_APPS: list[str] = []

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./db.sqlite3"
    # Several databases, by alias, each a URL like DATABASE_URL. Leave empty and
    # DATABASE_URL is the only one. A "default" entry is required when set: every
    # query that does not name a database uses it.
    # Each value is the URL, or {"URL": ..., "OPTIONS": {...}} where OPTIONS is
    # handed to SQLAlchemy's create_async_engine -- pool sizing, isolation_level,
    # or connect_args for the driver itself.
    DATABASES: dict[str, str | dict] = {}
    # The same OPTIONS for the single-database DATABASE_URL form.
    DATABASE_OPTIONS: dict = {}
    # Aliases from DATABASES that reads may be sent to, in rotation. Writes, and
    # reads inside atomic(), always go to "default".
    DATABASE_READ_REPLICAS: list[str] = []
    # Ignored by SQLite, which uses a StaticPool.
    # The implicit primary key on every model. Integer runs out near two
    # billion rows; set "buraq.orm.fields.BigAutoField" to start wider.
    DEFAULT_AUTO_FIELD: str = "buraq.orm.fields.AutoField"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    # Retire a pooled connection after this many seconds. Below MySQL's eight-hour
    # wait_timeout, so a connection is replaced before the server closes it.
    DATABASE_POOL_RECYCLE: int = 3600
    # Log every statement the engine emits. Tied to DEBUG previously, which
    # meant management commands buried their own output in SQL.
    DATABASE_ECHO: bool = False

    # Auth
    AUTH_USER_MODEL: str = "buraq.contrib.auth.models.User"
    PASSWORD_RESET_TIMEOUT: int = 259200  # 3 days in seconds
    AUTHENTICATION_BACKENDS: list[str] = ["buraq.contrib.auth.backends.ModelBackend"]
    AUTH_PASSWORD_VALIDATORS: list[dict] = [
        {"NAME": "buraq.contrib.auth.password_validation.MinimumLengthValidator"},
        {"NAME": "buraq.contrib.auth.password_validation.CommonPasswordValidator"},
        {"NAME": "buraq.contrib.auth.password_validation.NumericPasswordValidator"},
    ]

    # Middleware, outermost first -- the entry at the top sees a request before
    # every entry below it, and its response last. Order carries meaning: a
    # middleware reading request.session must sit below SessionMiddleware.
    MIDDLEWARE: list[str] = [
        "buraq.middleware.security.SecurityMiddleware",
        "buraq.middleware.cors.CORSMiddleware",
        "buraq.contrib.sessions.middleware.SessionMiddleware",
        # Reads the session, so it has to sit inside SessionMiddleware. Without
        # it request.user raises rather than returning AnonymousUser.
        "buraq.contrib.auth.middleware.AuthenticationMiddleware",
        # On by default, the way it is in the frameworks this follows: sessions
        # are cookie-based, so an unguarded POST is forgeable. A view that is
        # authenticated some other way -- a webhook, a bearer token -- opts out
        # with @csrf_exempt.
        "buraq.middleware.csrf.CsrfViewMiddleware",
        "buraq.middleware.gzip.GZipMiddleware",
    ]

    # CORS
    CORS_ORIGINS: list[str] = []
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]

    # Rate limiting
    RATE_LIMIT: str = "100/minute"

    # Static & templates
    # Whether the application serves static and media files itself. False for a
    # project that serves no files -- a JSON API -- or one where a web server
    # in front handles them.
    SERVE_STATIC: bool = True
    # Cache-Control lifetime for static files in production. collectstatic
    # writes content-hashed names, so a changed file arrives under a new URL
    # and a long lifetime is safe.
    # None picks by storage: a year (immutable) when names are hashed, a
    # minute when they are not, since the same URL then serves new bytes.
    STATIC_MAX_AGE: int | None = None
    STATIC_URL: str = "/static/"
    STATIC_DIR: str | None = None          # single source dir (legacy; prefer STATICFILES_DIRS)
    STATICFILES_DIRS: list[str] = []       # additional static source directories
    STATICFILES_FINDERS: list[str] = [
        "buraq.contrib.staticfiles.finders.FileSystemFinder",
        "buraq.contrib.staticfiles.finders.AppDirectoriesFinder",
    ]
    STATICFILES_STORAGE: str = "buraq.contrib.staticfiles.storage.StaticFilesStorage"
    # One path, or several when a project has more than one template root
    # -- its own beside a shared theme, say. Searched in the order given.
    TEMPLATES_DIR: str | list[str] | None = None
    MEDIA_URL: str = "/media/"
    MEDIA_DIR: str | None = None

    # Email
    EMAIL_BACKEND: str = "buraq.contrib.email.backends.smtp.SMTPEmailBackend"
    DEFAULT_FROM_EMAIL: str = "webmaster@localhost"
    EMAIL_FILE_PATH: str | None = None
    EMAIL_HOST: str | None = None
    EMAIL_PORT: int = 587
    EMAIL_HOST_USER: str | None = None
    EMAIL_HOST_PASSWORD: str | None = None
    EMAIL_USE_TLS: bool = True

    # Multiple mailers — dict of named backend configurations.
    # Each entry: {"BACKEND": "...", "HOST": "...", "PORT": 587, ...}
    # Use send_mail(..., using="name") to select a specific mailer.
    MAILERS: dict = {}

    # Cache
    CACHE_BACKEND: str = "buraq.contrib.cache.backends.memory.MemoryCacheBackend"
    CACHE_REDIS_URL: str | None = None
    CACHE_KEY_PREFIX: str = ""
    CACHE_FILE_PATH: str | None = None
    CACHE_DEFAULT_TIMEOUT: int = 300
    CACHE_TABLE: str = "buraq_cache_table"
    CACHE_CULL_PROBABILITY: float = 0.1
    CACHE_MEMCACHED_SERVERS: list[str] | None = None
    CACHE_MEMCACHED_URL: str | None = None
    CACHES: dict = {}

    # Sessions
    # JSON Web Tokens, signed with SECRET_KEY. HMAC only -- an asymmetric
    # algorithm needs a keypair rather than a secret.
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60
    SESSION_ENGINE: str = "buraq.contrib.sessions.backends.db"
    SESSION_COOKIE_NAME: str = "session"
    SESSION_COOKIE_MAX_AGE: int = 60 * 60 * 24 * 14  # 2 weeks
    SESSION_COOKIE_SAMESITE: str = "lax"
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_CACHE_ALIAS: str = "default"
    SESSION_FILE_PATH: str | None = None

    # URLs
    ROOT_URLCONF: str | None = None
    # Buraq registers every route without a trailing slash, so there is
    # nothing to append one to. Kept for projects that route both ways.
    APPEND_SLASH: bool = False
    PREPEND_WWW: bool = False

    # Templates
    APP_DIRS: bool = True
    # Passed to the Jinja environment: undefined, trim_blocks, lstrip_blocks,
    # autoescape, and an "extensions" list of dotted paths. Anything Jinja's
    # Environment accepts works here.
    TEMPLATE_OPTIONS: dict = {}

    # Content Security Policy
    CONTENT_SECURITY_POLICY: dict | None = None
    CONTENT_SECURITY_POLICY_REPORT_ONLY: dict | None = None
    CONTENT_SECURITY_POLICY_NONCE_DIRECTIVES: list[str] = []

    # Error reporting
    ADMINS: list = []
    MANAGERS: list = []

    # Files, tasks and number formatting
    DEFAULT_FILE_STORAGE: str | None = None
    TASKS: dict = {}
    NUMBER_GROUPING: int = 3
    DECIMAL_SEPARATOR: str = "."
    THOUSAND_SEPARATOR: str = ","

    # Static files
    STATIC_ROOT: str | None = None

    # Security headers (SecurityMiddleware)
    SECURE_HSTS_SECONDS: int = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS: bool = False
    SECURE_HSTS_PRELOAD: bool = False
    SECURE_CONTENT_TYPE_NOSNIFF: bool = True
    SECURE_REFERRER_POLICY: str = "same-origin"
    SECURE_CROSS_ORIGIN_OPENER_POLICY: str = "same-origin"
    SECURE_SSL_REDIRECT: bool = False
    SECURE_PERMISSIONS_POLICY: dict = {}
    X_FRAME_OPTIONS: str = "SAMEORIGIN"

    # Template context processors
    TEMPLATE_CONTEXT_PROCESSORS: list[str] = [
        "buraq.template.context_processors.request",
        "buraq.template.context_processors.auth",
    ]

    # Timezone
    USE_TZ: bool = True
    TIME_ZONE: str = "UTC"

    # Internationalization
    USE_I18N: bool = True
    LANGUAGE_CODE: str = "en"
    LANGUAGES: list[tuple[str, str]] = [
        ("en", "English"),
        ("ar", "العربية"),
        ("fr", "Français"),
        ("es", "Español"),
        ("de", "Deutsch"),
        ("zh", "中文"),
        ("ja", "日本語"),
        ("tr", "Türkçe"),
        ("ur", "اردو"),
    ]
    LOCALE_PATHS: list[str] = []
    LANGUAGE_COOKIE_NAME: str = "buraq_language"
    LANGUAGE_COOKIE_AGE: int = 60 * 60 * 24 * 365  # 1 year


# Global settings instance — overridden by user's settings module
settings = BuraqSettings()

# An insecure SECRET_KEY is caught by the system checks (security.E001), which
# run at application startup and refuse to serve when DEBUG is off. Raising here
# instead would fire on `import buraq`, so a machine with no project configured
# could not even run `buraq startproject` -- the first command anyone types.
