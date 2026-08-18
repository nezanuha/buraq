"""
BuraqJSONEncoder — stdlib json.JSONEncoder with extra type support.

Usage:
    import json
    from buraq.utils.json import BuraqJSONEncoder

    json.dumps({"ts": datetime.now()}, cls=BuraqJSONEncoder)
"""
from __future__ import annotations

import datetime
import decimal
import json
import uuid


class BuraqJSONEncoder(json.JSONEncoder):
    """
    JSONEncoder subclass that handles types the stdlib encoder cannot:

    - ``datetime.datetime`` / ``datetime.date`` / ``datetime.time`` → ISO 8601
    - ``datetime.timedelta`` → total seconds (float)
    - ``decimal.Decimal`` → string
    - ``uuid.UUID`` → string
    - Objects with a ``__json__()`` method → its return value

    For ``datetime`` and ``time`` objects, the millisecond (microsecond) component
    is omitted when it is zero.
    """

    def default(self, o):
        if isinstance(o, datetime.datetime):
            return _datetime_isoformat(o)
        if isinstance(o, datetime.date):
            return o.isoformat()
        if isinstance(o, datetime.time):
            return _time_isoformat(o)
        if isinstance(o, datetime.timedelta):
            return o.total_seconds()
        if isinstance(o, decimal.Decimal):
            return str(o)
        if isinstance(o, uuid.UUID):
            return str(o)
        if hasattr(o, "__json__"):
            return o.__json__()
        return super().default(o)


def _datetime_isoformat(dt: datetime.datetime) -> str:
    if dt.microsecond == 0:
        return dt.strftime("%Y-%m-%dT%H:%M:%S") + _tzinfo_suffix(dt)
    return dt.isoformat()


def _time_isoformat(t: datetime.time) -> str:
    if t.microsecond == 0:
        return t.strftime("%H:%M:%S") + _tzinfo_suffix(t)
    return t.isoformat()


def _tzinfo_suffix(obj) -> str:
    tz = getattr(obj, "tzinfo", None)
    if tz is None:
        return ""
    utc_offset = tz.utcoffset(obj if isinstance(obj, datetime.datetime) else None)
    if utc_offset is None:
        return ""
    if utc_offset == datetime.timedelta(0):
        return "+00:00"
    total = int(utc_offset.total_seconds())
    sign = "+" if total >= 0 else "-"
    total = abs(total)
    return f"{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}"


__all__ = ["BuraqJSONEncoder"]
