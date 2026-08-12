"""
Date/time string parsing utilities.

Usage:
    from buraq.utils.dateparse import parse_date, parse_datetime, parse_duration
"""
from __future__ import annotations

import re
from datetime import UTC, date, datetime, time, timedelta, timezone

# ISO 8601 patterns
_DATE_RE = re.compile(r"(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})$")

_TIME_RE = re.compile(
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})"
    r"(?::(?P<second>\d{2})(?:[.,](?P<microsecond>\d{1,6}))?)?"
    r"\s*(?P<tzinfo>Z|[+-]\d{2}:?\d{2})?$"
)

_DATETIME_RE = re.compile(
    r"(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})"
    r"[T ]"
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})"
    r"(?::(?P<second>\d{2})(?:[.,](?P<microsecond>\d{1,6}))?)?"
    r"\s*(?P<tzinfo>Z|[+-]\d{2}:?\d{2})?$"
)

_DURATION_RE = re.compile(
    r"^(?P<sign>[-+]?)P"
    r"(?:(?P<years>\d+(?:\.\d+)?)Y)?"
    r"(?:(?P<months>\d+(?:\.\d+)?)M)?"
    r"(?:(?P<weeks>\d+(?:\.\d+)?)W)?"
    r"(?:(?P<days>\d+(?:\.\d+)?)D)?"
    r"(?:T"
    r"(?:(?P<hours>\d+(?:\.\d+)?)H)?"
    r"(?:(?P<minutes>\d+(?:\.\d+)?)M)?"
    r"(?:(?P<seconds>\d+(?:\.\d+)?)S)?"
    r")?$"
)

# Pure ISO 8601 week period: P2W, P1.5W, -P3W
_WEEK_ONLY_RE = re.compile(r"^(?P<sign>[-+]?)P(?P<weeks>\d+(?:\.\d+)?)W$")

_SIMPLE_DURATION_RE = re.compile(
    r"^(?P<sign>[-+]?)(?:(?P<days>\d+) )?"
    r"(?P<hours>\d+):(?P<minutes>\d{2}):(?P<seconds>\d{2})"
    r"(?:[.,](?P<microseconds>\d{1,6}))?$"
)


def _parse_tz(tzstr: str | None) -> timezone | None:
    if not tzstr:
        return None
    if tzstr in ("Z", "+00:00", "-00:00"):
        return UTC
    sign = 1 if tzstr[0] == "+" else -1
    parts = tzstr[1:].replace(":", "")
    hours = int(parts[:2])
    minutes = int(parts[2:4]) if len(parts) >= 4 else 0
    return timezone(sign * timedelta(hours=hours, minutes=minutes))


def parse_date(value: str) -> date | None:
    """Parse an ISO 8601 date string into a ``date`` object, or return None."""
    if not value:
        return None
    m = _DATE_RE.match(value.strip())
    if not m:
        return None
    try:
        return date(int(m["year"]), int(m["month"]), int(m["day"]))
    except ValueError:
        return None


def parse_time(value: str) -> time | None:
    """Parse an ISO 8601 time string into a ``time`` object, or return None."""
    if not value:
        return None
    m = _TIME_RE.match(value.strip())
    if not m:
        return None
    try:
        us_str = m["microsecond"] or ""
        us = int(us_str.ljust(6, "0")) if us_str else 0
        tz = _parse_tz(m["tzinfo"])
        return time(
            int(m["hour"]),
            int(m["minute"]),
            int(m["second"] or 0),
            us,
            tzinfo=tz,
        )
    except ValueError:
        return None


def parse_datetime(value: str) -> datetime | None:
    """Parse an ISO 8601 datetime string into a ``datetime`` object, or return None."""
    if not value:
        return None
    m = _DATETIME_RE.match(value.strip())
    if not m:
        return None
    try:
        us_str = m["microsecond"] or ""
        us = int(us_str.ljust(6, "0")) if us_str else 0
        tz = _parse_tz(m["tzinfo"])
        return datetime(
            int(m["year"]),
            int(m["month"]),
            int(m["day"]),
            int(m["hour"]),
            int(m["minute"]),
            int(m["second"] or 0),
            us,
            tzinfo=tz,
        )
    except ValueError:
        return None


def parse_duration(value: str) -> timedelta | None:
    """
    Parse a duration string into a ``timedelta``.

    Accepts ISO 8601 durations (``P1DT2H3M4S``) and
    simple ``[[DD ]HH:MM:SS[.uuuuuu]]`` format.
    """
    if not value:
        return None
    value = value.strip()

    # ISO 8601 week-only period: P2W, P1.5W
    m = _WEEK_ONLY_RE.match(value)
    if m:
        sign = -1 if m["sign"] == "-" else 1
        return sign * timedelta(weeks=float(m["weeks"]))

    # Try simple HH:MM:SS format first
    m = _SIMPLE_DURATION_RE.match(value)
    if m:
        sign = -1 if m["sign"] == "-" else 1
        days = int(m["days"] or 0)
        hours = int(m["hours"])
        minutes = int(m["minutes"])
        seconds = int(m["seconds"])
        us = int((m["microseconds"] or "").ljust(6, "0")[:6])
        return sign * timedelta(
            days=days, hours=hours, minutes=minutes, seconds=seconds, microseconds=us
        )

    # Try ISO 8601 P...T... format
    m = _DURATION_RE.match(value)
    if not m:
        return None
    sign = -1 if m["sign"] == "-" else 1
    weeks = float(m["weeks"] or 0)
    days = float(m["days"] or 0) + float(m["months"] or 0) * 30 + float(m["years"] or 0) * 365
    hours = float(m["hours"] or 0)
    minutes = float(m["minutes"] or 0)
    seconds = float(m["seconds"] or 0)
    return sign * timedelta(weeks=weeks, days=days, hours=hours, minutes=minutes, seconds=seconds)


__all__ = ["parse_date", "parse_time", "parse_datetime", "parse_duration"]
