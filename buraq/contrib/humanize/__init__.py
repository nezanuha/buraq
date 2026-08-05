"""
Human-readable number, date, and time formatting.

Usage:
    from buraq.contrib.humanize import intcomma, naturaltime, ordinal

    intcomma(1234567)    # → "1,234,567"
    ordinal(3)           # → "3rd"
    naturaltime(dt)      # → "2 hours ago"
"""
from __future__ import annotations

from datetime import date, datetime, timedelta


def intcomma(value: int | float | str) -> str:
    """Format an integer with thousands separators: ``1234567`` → ``"1,234,567"``."""
    try:
        value = int(value)
    except (ValueError, TypeError):
        return str(value)
    return f"{value:,}"


def ordinal(value: int | str) -> str:
    """Return the ordinal string of an integer: ``1`` → ``"1st"``."""
    try:
        n = int(value)
    except (ValueError, TypeError):
        return str(value)
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def apnumber(value: int | str) -> str:
    """
    Convert small numbers to their AP style word: ``1`` → ``"one"``.

    Numbers 10 and above are returned as digits.
    """
    _AP = ["zero", "one", "two", "three", "four", "five",
           "six", "seven", "eight", "nine"]
    try:
        n = int(value)
    except (ValueError, TypeError):
        return str(value)
    if 0 <= n < len(_AP):
        return _AP[n]
    return str(n)


def pluralize(value: int | float, singular: str = "", plural: str = "s") -> str:
    """
    Return the plural suffix if ``value != 1``.

        f"You have {count} message{pluralize(count)}."
        f"You have {count} {pluralize(count, 'match', 'matches')}."
    """
    try:
        n = int(value)
    except (ValueError, TypeError):
        return plural
    return singular if n == 1 else plural


def naturalday(value: date, format: str = "%b %d") -> str:
    """
    For datetimes that are close to now, return "today", "yesterday", or "tomorrow";
    otherwise format with ``format``.
    """
    today = date.today()
    if isinstance(value, datetime):
        value = value.date()
    delta = value - today
    if delta.days == 0:
        return "today"
    if delta.days == -1:
        return "yesterday"
    if delta.days == 1:
        return "tomorrow"
    return value.strftime(format)


def naturaltime(value: datetime, now: datetime = None) -> str:
    """
    Return a human-readable time delta relative to now.

        naturaltime(datetime.now() - timedelta(hours=2))
        # → "2 hours ago"

        naturaltime(datetime.now() + timedelta(minutes=5))
        # → "5 minutes from now"
    """
    if now is None:
        now = datetime.now(tz=value.tzinfo) if value.tzinfo else datetime.now()

    delta = now - value
    future = delta.total_seconds() < 0
    seconds = abs(delta.total_seconds())

    if seconds < 10:
        return "just now"

    chunks = [
        (365 * 24 * 3600, "year"),
        (30 * 24 * 3600, "month"),
        (7 * 24 * 3600, "week"),
        (24 * 3600, "day"),
        (3600, "hour"),
        (60, "minute"),
        (1, "second"),
    ]

    for threshold, name in chunks:
        count = int(seconds / threshold)
        if count >= 1:
            noun = name if count == 1 else f"{name}s"
            if future:
                return f"{count} {noun} from now"
            return f"{count} {noun} ago"

    return "just now"


def naturalduration(value: timedelta) -> str:
    """
    Return a human-readable duration string.

        naturalduration(timedelta(hours=1, minutes=30))
        # → "1 hour, 30 minutes"
    """
    if not isinstance(value, timedelta):
        return str(value)
    total_seconds = int(abs(value.total_seconds()))
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds and not parts:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

    return ", ".join(parts) if parts else "0 seconds"


def intword(value: int | float | str) -> str:
    """
    Convert a large integer to a friendly string: ``1200000`` → ``"1.2 million"``.
    """
    try:
        n = float(value)
    except (ValueError, TypeError):
        return str(value)

    _POWERS = [
        (10**12, "trillion"),
        (10**9, "billion"),
        (10**6, "million"),
        (10**3, "thousand"),
    ]
    for power, name in _POWERS:
        if abs(n) >= power:
            rounded = round(n / power, 1)
            return f"{rounded:g} {name}"
    return str(int(n))


__all__ = [
    "intcomma", "ordinal", "apnumber", "pluralize",
    "naturalday", "naturaltime", "naturalduration", "intword",
]
