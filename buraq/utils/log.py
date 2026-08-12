"""
Logging utilities — mirrors django.utils.log.

Usage::

    from buraq.utils.log import AdminEmailHandler, configure_logging

    # In settings.py:
    LOGGING = {
        "version": 1,
        "handlers": {
            "mail_admins": {
                "level": "ERROR",
                "class": "buraq.utils.log.AdminEmailHandler",
                "include_html": False,
            },
        },
        "loggers": {
            "buraq.request": {"handlers": ["mail_admins"], "level": "ERROR"},
        },
    }
"""
from __future__ import annotations

import contextlib
import logging
import traceback


class AdminEmailHandler(logging.Handler):
    """
    Email log records of level ERROR (and above) to ADMINS.

    Configure via the standard ``logging.config.dictConfig()`` dictionary.
    """

    def __init__(self, include_html: bool = False, email_backend: str | None = None):
        super().__init__()
        self.include_html = include_html
        self.email_backend = email_backend

    def emit(self, record: logging.LogRecord) -> None:
        try:
            subject = f"[Buraq ERROR] {record.getMessage()[:50]}"
            body = self.format(record)
            if record.exc_info:
                body += "\n\n" + "".join(traceback.format_exception(*record.exc_info))
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._send(subject, body))
            except RuntimeError:
                asyncio.run(self._send(subject, body))
        except Exception:
            self.handleError(record)

    async def _send(self, subject: str, body: str) -> None:
        from buraq.contrib.email.send import mail_admins
        with contextlib.suppress(Exception):
            await mail_admins(subject, body)


class RequireDebugFalse(logging.Filter):
    """Passes only when ``DEBUG=False``."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from buraq.conf import settings
            return not settings.DEBUG
        except Exception:
            return True


class RequireDebugTrue(logging.Filter):
    """Passes only when ``DEBUG=True``."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from buraq.conf import settings
            return bool(settings.DEBUG)
        except Exception:
            return False


def configure_logging(logging_config: str | None, logging_settings: dict | None) -> None:
    """Apply the ``LOGGING`` dict from settings using ``logging.config.dictConfig``."""
    if not logging_settings:
        return
    import logging.config
    logging.config.dictConfig(logging_settings)
