"""Built-in security checks — registered automatically on import."""
from __future__ import annotations

from buraq.checks.registry import Error, Warning, registry


@registry.register
def check_secret_key(settings, **kwargs):
    errors = []
    if not settings.SECRET_KEY or settings.SECRET_KEY == "change-me-in-production":
        errors.append(Error(
            "SECRET_KEY is set to the insecure default value.",
            hint="Set a strong random SECRET_KEY in your .env before deploying.",
            id="security.E001",
        ))
    elif len(settings.SECRET_KEY) < 50:
        errors.append(Warning(
            "SECRET_KEY is shorter than 50 characters.",
            hint="Use a longer random key for better security.",
            id="security.W001",
        ))
    return errors


@registry.register
def check_debug_allowed_hosts(settings, **kwargs):
    if settings.DEBUG and settings.ALLOWED_HOSTS == ["*"]:
        return [Warning(
            "DEBUG=True with ALLOWED_HOSTS=['*'] is not safe for production.",
            hint="Set ALLOWED_HOSTS to your domain and DEBUG=False before deploying.",
            id="security.W002",
        )]
    return []


@registry.register
def check_database_url(settings, **kwargs):
    url = getattr(settings, "DATABASE_URL", "")
    if "sqlite" in url and not getattr(settings, "DEBUG", True):
        return [Warning(
            "SQLite is configured in a non-DEBUG environment.",
            hint="Use PostgreSQL or another production-grade database.",
            id="database.W001",
        )]
    return []
