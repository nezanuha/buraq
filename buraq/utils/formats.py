"""
Locale-aware format functions — mirrors django.utils.formats.

Usage::

    from buraq.utils.formats import number_format, date_format, time_format

    number_format(1234.5)          # "1,234.5"
    date_format(date.today(), "N j, Y")
"""
from __future__ import annotations

import datetime

# Default format strings (ASCII-safe)
DATE_FORMAT = "N j, Y"
TIME_FORMAT = "P"
DATETIME_FORMAT = "N j, Y, P"
SHORT_DATE_FORMAT = "m/d/Y"
SHORT_DATETIME_FORMAT = "m/d/Y P"
NUMBER_GROUPING = 3
DECIMAL_SEPARATOR = "."
THOUSAND_SEPARATOR = ","


def get_format(format_type: str, lang: str | None = None, use_l10n: bool | None = None) -> str:
    """Return the format string for the given type."""
    _defaults = {
        "DATE_FORMAT": DATE_FORMAT,
        "TIME_FORMAT": TIME_FORMAT,
        "DATETIME_FORMAT": DATETIME_FORMAT,
        "SHORT_DATE_FORMAT": SHORT_DATE_FORMAT,
        "SHORT_DATETIME_FORMAT": SHORT_DATETIME_FORMAT,
    }
    try:
        from buraq.conf import settings
        return getattr(settings, format_type, _defaults.get(format_type, ""))
    except Exception:
        return _defaults.get(format_type, "")


def date_format(value, format: str | None = None, use_l10n: bool | None = None) -> str:
    """Format a date using Django-style format codes."""
    from buraq.template.builtins import _format_date
    fmt = format or get_format("DATE_FORMAT")
    return _format_date(value, fmt)


def time_format(value, format: str | None = None, use_l10n: bool | None = None) -> str:
    """Format a time value."""
    from buraq.template.builtins import time_filter
    fmt = format or get_format("TIME_FORMAT")
    return time_filter(value, fmt)


def number_format(
    value,
    decimal_pos: int | None = None,
    use_l10n: bool | None = None,
    force_grouping: bool = False,
) -> str:
    """Format a number with locale-aware separators."""
    from buraq.utils.numberformat import format as _fmt
    try:
        from buraq.conf import settings
        dec_sep = getattr(settings, "DECIMAL_SEPARATOR", DECIMAL_SEPARATOR)
        thou_sep = getattr(settings, "THOUSAND_SEPARATOR", THOUSAND_SEPARATOR)
        grouping = getattr(settings, "NUMBER_GROUPING", NUMBER_GROUPING)
    except Exception:
        dec_sep, thou_sep, grouping = DECIMAL_SEPARATOR, THOUSAND_SEPARATOR, NUMBER_GROUPING
    return _fmt(value, dec_sep, decimal_pos or 2, grouping, thou_sep, force_grouping)


def localize(value, use_l10n: bool | None = None) -> str:
    """Localize a value (date, number, etc.) to a string."""
    if isinstance(value, datetime.datetime):
        return date_format(value, get_format("DATETIME_FORMAT"))
    if isinstance(value, datetime.date):
        return date_format(value)
    if isinstance(value, datetime.time):
        return time_format(value)
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return number_format(value)
    return str(value)
