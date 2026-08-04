"""
Timezone utilities — now(), localtime(), make_aware(), and context-local activation.

Uses Python's stdlib ``zoneinfo`` module (C extension, Python 3.9+, zero extra deps).
Uses ``contextvars`` for async-safe per-request timezone state.

Usage:
    from buraq.utils.timezone import now, localtime, make_aware, override
"""
from __future__ import annotations

import contextvars
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

# UTC singleton — same as datetime.timezone.utc but named for clarity
UTC = UTC

_active_timezone: contextvars.ContextVar[ZoneInfo | None] = contextvars.ContextVar(
    "_active_timezone", default=None
)


# ── Settings helpers ───────────────────────────────────────────────────────────

def _settings_tz() -> ZoneInfo:
    from buraq.conf.defaults import settings
    return ZoneInfo(getattr(settings, "TIME_ZONE", "UTC"))


def _use_tz() -> bool:
    from buraq.conf.defaults import settings
    return getattr(settings, "USE_TZ", True)


# ── Active timezone ────────────────────────────────────────────────────────────

def get_current_timezone() -> ZoneInfo:
    """Return the active timezone (from override() or TIME_ZONE setting)."""
    return _active_timezone.get() or _settings_tz()


def get_current_timezone_name() -> str:
    """Return the active timezone name, e.g. ``"America/New_York"``."""
    return str(get_current_timezone())


def activate(timezone: ZoneInfo | str) -> contextvars.Token:
    """
    Activate a timezone for the current async context.
    Returns a token — pass it to ``deactivate()`` to restore the previous timezone.
    """
    if isinstance(timezone, str):
        timezone = ZoneInfo(timezone)
    return _active_timezone.set(timezone)


def deactivate(token: contextvars.Token) -> None:
    """Restore the previous timezone using the token returned by ``activate()``."""
    _active_timezone.reset(token)


@contextmanager
def override(timezone: ZoneInfo | str) -> Generator[None, None, None]:
    """
    Context manager — temporarily activate a timezone::

        from buraq.utils.timezone import override, localtime

        with override("America/New_York"):
            print(localtime())   # current time in New York

        # async tasks
        with override("Asia/Tokyo"):
            dt = localtime(some_utc_datetime)
    """
    token = activate(timezone)
    try:
        yield
    finally:
        deactivate(token)


# ── Core functions ─────────────────────────────────────────────────────────────

def now() -> datetime:
    """
    Return the current date and time.

    Returns a timezone-aware UTC datetime when ``USE_TZ = True`` (default),
    or a naive local datetime when ``USE_TZ = False``.
    """
    if _use_tz():
        return datetime.now(tz=UTC)
    return datetime.now()


def localtime(value: datetime | None = None, timezone: ZoneInfo | str | None = None) -> datetime:
    """
    Convert an aware datetime to the active timezone (or ``timezone`` if given).

    If ``value`` is None, uses the current time.

    Usage::

        dt = localtime()                        # now in current timezone
        dt = localtime(some_utc_dt, "Asia/Tokyo")
    """
    if value is None:
        value = now()
    if isinstance(timezone, str):
        timezone = ZoneInfo(timezone)
    tz = timezone or get_current_timezone()
    return value.astimezone(tz)


def localdate(value: datetime | None = None, timezone: ZoneInfo | str | None = None) -> date:
    """Return the local date for a datetime (today by default)."""
    return localtime(value, timezone).date()


def make_aware(value: datetime, timezone: ZoneInfo | str | None = None) -> datetime:
    """
    Make a naive datetime timezone-aware.

    If ``value`` is already aware, convert it to the target timezone.
    """
    if isinstance(timezone, str):
        timezone = ZoneInfo(timezone)
    tz = timezone or get_current_timezone()
    if is_aware(value):
        return value.astimezone(tz)
    return value.replace(tzinfo=tz)


def make_naive(value: datetime, timezone: ZoneInfo | str | None = None) -> datetime:
    """
    Make an aware datetime naive by converting to the target timezone and stripping tzinfo.
    """
    if isinstance(timezone, str):
        timezone = ZoneInfo(timezone)
    tz = timezone or get_current_timezone()
    return value.astimezone(tz).replace(tzinfo=None)


def is_aware(value: datetime) -> bool:
    """Return True if the datetime has timezone info."""
    return value.tzinfo is not None and value.tzinfo.utcoffset(value) is not None


def is_naive(value: datetime) -> bool:
    """Return True if the datetime has no timezone info."""
    return not is_aware(value)
