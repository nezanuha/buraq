import warnings

from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRET_KEY = "change-me-in-production"


class BuraqSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",
    )

    # Core
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    ALLOWED_HOSTS: list[str] = ["*"]
    INSTALLED_APPS: list[str] = []

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./db.sqlite3"

    # Auth
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    ALGORITHM: str = "HS256"

    # CORS
    CORS_ORIGINS: list[str] = []
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]

    # Rate limiting
    RATE_LIMIT: str = "100/minute"

    # Static & templates
    STATIC_URL: str = "/static/"
    STATIC_DIR: str | None = None
    TEMPLATES_DIR: str | None = None
    MEDIA_URL: str = "/media/"
    MEDIA_DIR: str | None = None

    # Email
    EMAIL_BACKEND: str = "buraq.contrib.email.backends.smtp.EmailBackend"
    DEFAULT_FROM_EMAIL: str = "webmaster@localhost"
    EMAIL_FILE_PATH: str | None = None
    EMAIL_HOST: str | None = None
    EMAIL_PORT: int = 587
    EMAIL_HOST_USER: str | None = None
    EMAIL_HOST_PASSWORD: str | None = None
    EMAIL_USE_TLS: bool = True

    # Cache
    CACHE_BACKEND: str = "buraq.contrib.cache.backends.memory.MemoryCache"
    CACHE_REDIS_URL: str | None = None
    CACHE_KEY_PREFIX: str = ""
    CACHE_FILE_PATH: str | None = None
    CACHE_DEFAULT_TIMEOUT: int = 300

    # Static files
    STATIC_ROOT: str | None = None

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

if settings.SECRET_KEY == _INSECURE_SECRET_KEY:
    warnings.warn(
        "SECRET_KEY is set to the default insecure value. "
        "Set a strong SECRET_KEY in your .env file before deploying to production.",
        stacklevel=2,
    )
