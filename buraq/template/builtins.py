"""
Built-in template filters — Django-compatible set for Jinja2.

Registered automatically into every Jinja2 environment via get_templates().
Import and call register_builtins(env) to apply manually.
"""
from __future__ import annotations

import datetime
import json
import math
import re
import unicodedata
from html import escape as html_escape


# ── Date / time formatting ────────────────────────────────────────────────────

_MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_MONTH_ABBR = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]
_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_DAY_ABBR  = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

_ORDINALS = {1: "st", 2: "nd", 3: "rd"}


def _ordinal_suffix(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return "th"
    return _ORDINALS.get(n % 10, "th")


def _format_date(value, fmt: str) -> str:
    """
    Format a date/datetime using Django-style format codes.

    Supported codes:
      d  — day (01-31)        j  — day (1-31)          N  — month abbr (Jan…)
      D  — weekday abbr       l  — weekday full         m  — month (01-12)
      n  — month (1-12)       M  — month abbr           F  — month full
      Y  — 4-digit year       y  — 2-digit year         G  — 24h hour (0-23)
      H  — 24h hour (00-23)   g  — 12h hour (1-12)      h  — 12h hour (01-12)
      i  — minutes (00-59)    s  — seconds (00-59)      A  — AM/PM
      a  — am/pm              S  — ordinal suffix        U  — Unix timestamp
      W  — ISO week number     z  — day of year (0-365)  t  — days in month
    """
    if value is None:
        return ""
    if isinstance(value, datetime.datetime):
        dt = value
    elif isinstance(value, datetime.date):
        dt = datetime.datetime(value.year, value.month, value.day)
    else:
        return str(value)

    result = []
    i = 0
    while i < len(fmt):
        c = fmt[i]
        if c == "\\":
            i += 1
            if i < len(fmt):
                result.append(fmt[i])
        elif c == "d":
            result.append(f"{dt.day:02d}")
        elif c == "j":
            result.append(str(dt.day))
        elif c == "D":
            result.append(_DAY_ABBR[dt.weekday()])
        elif c == "l":
            result.append(_DAY_NAMES[dt.weekday()])
        elif c == "S":
            result.append(_ordinal_suffix(dt.day))
        elif c == "m":
            result.append(f"{dt.month:02d}")
        elif c == "n":
            result.append(str(dt.month))
        elif c == "M":
            result.append(_MONTH_ABBR[dt.month])
        elif c == "N":
            result.append(_MONTH_ABBR[dt.month])
        elif c == "F":
            result.append(_MONTH_NAMES[dt.month])
        elif c == "Y":
            result.append(str(dt.year))
        elif c == "y":
            result.append(str(dt.year)[-2:])
        elif c == "H":
            result.append(f"{dt.hour:02d}")
        elif c == "G":
            result.append(str(dt.hour))
        elif c == "h":
            h = dt.hour % 12 or 12
            result.append(f"{h:02d}")
        elif c == "g":
            result.append(str(dt.hour % 12 or 12))
        elif c == "i":
            result.append(f"{dt.minute:02d}")
        elif c == "s":
            result.append(f"{dt.second:02d}")
        elif c == "A":
            result.append("AM" if dt.hour < 12 else "PM")
        elif c == "a":
            result.append("am" if dt.hour < 12 else "pm")
        elif c == "U":
            result.append(str(int(dt.timestamp())))
        elif c == "W":
            result.append(str(dt.isocalendar()[1]))
        elif c == "z":
            result.append(str(dt.timetuple().tm_yday - 1))
        elif c == "t":
            import calendar
            result.append(str(calendar.monthrange(dt.year, dt.month)[1]))
        elif c == "e":
            result.append(dt.tzname() or "")
        elif c == "T":
            result.append(dt.strftime("%Z") or "")
        else:
            result.append(c)
        i += 1
    return "".join(result)


def date_filter(value, fmt: str = "N j, Y") -> str:
    """Format a date or datetime using Django date format codes."""
    return _format_date(value, fmt)


def time_filter(value, fmt: str = "P") -> str:
    """Format a time or datetime using Django time format codes."""
    if fmt == "P":
        fmt = "g:i A"
    return _format_date(value, fmt)


# ── timesince / timeuntil ─────────────────────────────────────────────────────

def _time_chunks():
    return [
        (60 * 60 * 24 * 365, "year"),
        (60 * 60 * 24 * 30,  "month"),
        (60 * 60 * 24 * 7,   "week"),
        (60 * 60 * 24,       "day"),
        (60 * 60,            "hour"),
        (60,                 "minute"),
    ]


def _since(d, now=None, reversed_=False):
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    if isinstance(d, datetime.date) and not isinstance(d, datetime.datetime):
        d = datetime.datetime(d.year, d.month, d.day, tzinfo=datetime.timezone.utc)
    if isinstance(now, datetime.date) and not isinstance(now, datetime.datetime):
        now = datetime.datetime(now.year, now.month, now.day, tzinfo=datetime.timezone.utc)
    if d.tzinfo and not now.tzinfo:
        now = now.replace(tzinfo=datetime.timezone.utc)
    elif not d.tzinfo and now.tzinfo:
        d = d.replace(tzinfo=datetime.timezone.utc)

    delta = (now - d) if not reversed_ else (d - now)
    since = int(delta.total_seconds())
    if since <= 0:
        return "0 minutes"

    parts = []
    for seconds, name in _time_chunks():
        count = since // seconds
        if count:
            parts.append(f"{count} {name}{'s' if count != 1 else ''}")
            since -= count * seconds
            if len(parts) == 2:
                break
    return ", ".join(parts) if parts else "0 minutes"


def timesince_filter(value, now=None) -> str:
    """Return time elapsed since value as a human-readable string."""
    return _since(value, now)


def timeuntil_filter(value, now=None) -> str:
    """Return time until value as a human-readable string."""
    return _since(value, now, reversed_=True)


# ── Text ──────────────────────────────────────────────────────────────────────

def truncatechars_filter(value, length: int) -> str:
    s = str(value)
    length = int(length)
    return s if len(s) <= length else s[:max(0, length - 1)] + "…"


def truncatewords_filter(value, num: int) -> str:
    words = str(value).split()
    num = int(num)
    if len(words) <= num:
        return str(value)
    return " ".join(words[:num]) + " …"


def truncatechars_html_filter(value, length: int) -> str:
    from markupsafe import Markup
    text = re.sub(r"<[^>]+>", "", str(value))
    return Markup(truncatechars_filter(text, length))


def wordcount_filter(value) -> int:
    return len(str(value).split())


def capfirst_filter(value) -> str:
    s = str(value)
    return s[0].upper() + s[1:] if s else s


def addslashes_filter(value) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'")


def slugify_filter(value) -> str:
    s = str(value)
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    return re.sub(r"[-\s]+", "-", s)


def linenumbers_filter(value) -> str:
    from markupsafe import Markup
    lines = str(value).splitlines()
    width = len(str(len(lines)))
    numbered = [f"{i + 1:{width}}. {line}" for i, line in enumerate(lines)]
    return Markup("\n".join(numbered))


def pluralize_filter(value, arg: str = "s") -> str:
    parts = arg.split(",")
    singular = "" if len(parts) == 1 else parts[0]
    plural = parts[-1]
    try:
        num = int(value)
    except (TypeError, ValueError):
        try:
            num = len(value)
        except TypeError:
            return singular
    return singular if num == 1 else plural


def yesno_filter(value, arg: str = "yes,no,maybe") -> str:
    parts = arg.split(",")
    yes = parts[0] if len(parts) > 0 else "yes"
    no = parts[1] if len(parts) > 1 else "no"
    maybe = parts[2] if len(parts) > 2 else no
    if value is None:
        return maybe
    if value:
        return yes
    return no


def default_if_none_filter(value, default="") -> str:
    return default if value is None else value


def phone2numeric_filter(value) -> str:
    mapping = {
        "a": "2", "b": "2", "c": "2",
        "d": "3", "e": "3", "f": "3",
        "g": "4", "h": "4", "i": "4",
        "j": "5", "k": "5", "l": "5",
        "m": "6", "n": "6", "o": "6",
        "p": "7", "q": "7", "r": "7", "s": "7",
        "t": "8", "u": "8", "v": "8",
        "w": "9", "x": "9", "y": "9", "z": "9",
    }
    return "".join(mapping.get(c.lower(), c) for c in str(value))


# ── HTML ──────────────────────────────────────────────────────────────────────

def linebreaks_filter(value) -> str:
    from markupsafe import Markup
    s = html_escape(str(value))
    paragraphs = re.split(r"\n{2,}", s)
    result = []
    for p in paragraphs:
        p = p.replace("\n", "<br>")
        result.append(f"<p>{p}</p>")
    return Markup("\n\n".join(result))


def linebreaksbr_filter(value) -> str:
    from markupsafe import Markup
    return Markup(html_escape(str(value)).replace("\n", "<br>"))


def urlize_filter(value, autoescape: bool = True) -> str:
    from markupsafe import Markup
    text = str(value)
    url_re = re.compile(
        r"(https?://[^\s<>\"']+)"
    )
    email_re = re.compile(
        r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)"
    )

    def replace_url(m):
        url = m.group(1)
        return f'<a href="{html_escape(url)}" rel="nofollow">{html_escape(url)}</a>'

    def replace_email(m):
        email = m.group(1)
        return f'<a href="mailto:{html_escape(email)}">{html_escape(email)}</a>'

    escaped = html_escape(text) if autoescape else text
    result = url_re.sub(replace_url, escaped)
    result = email_re.sub(replace_email, result)
    return Markup(result)


def escapejs_filter(value) -> str:
    s = str(value)
    s = s.replace("\\", "\\u005C")
    s = s.replace("'", "\\u0027")
    s = s.replace('"', "\\u0022")
    s = s.replace("<", "\\u003C")
    s = s.replace(">", "\\u003E")
    s = s.replace("&", "\\u0026")
    s = s.replace("=", "\\u003D")
    s = s.replace("-", "\\u002D")
    s = s.replace(";", "\\u003B")
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    s = s.replace("\t", "\\t")
    return s


def json_script_filter(value, element_id: str) -> str:
    from markupsafe import Markup
    data = json.dumps(value, cls=_SafeJSONEncoder)
    safe_data = data.replace("<", "\\u003C").replace(">", "\\u003E").replace("&", "\\u0026")
    return Markup(f'<script id="{html_escape(element_id)}" type="application/json">{safe_data}</script>')


class _SafeJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        return super().default(obj)


# ── Numbers / sizes ───────────────────────────────────────────────────────────

def filesizeformat_filter(value) -> str:
    try:
        size = float(value)
    except (TypeError, ValueError):
        return "0 bytes"
    for unit, threshold in [
        ("PB", 1e15), ("TB", 1e12), ("GB", 1e9), ("MB", 1e6), ("KB", 1e3),
    ]:
        if size >= threshold:
            v = size / threshold
            return f"{v:.1f} {unit}" if v != int(v) else f"{int(v)} {unit}"
    return f"{int(size)} byte{'s' if size != 1 else ''}"


def floatformat_filter(value, precision: int = -1) -> str:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    precision = int(precision)
    if precision < 0:
        s = f"{f:.{-precision}f}"
        return s.rstrip("0").rstrip(".") or "0"
    return f"{f:.{precision}f}"


# ── Apply to Jinja2 env ───────────────────────────────────────────────────────

_FILTERS: dict = {
    "date":              date_filter,
    "time":              time_filter,
    "timesince":         timesince_filter,
    "timeuntil":         timeuntil_filter,
    "truncatechars":     truncatechars_filter,
    "truncatewords":     truncatewords_filter,
    "truncatechars_html": truncatechars_html_filter,
    "wordcount":         wordcount_filter,
    "capfirst":          capfirst_filter,
    "addslashes":        addslashes_filter,
    "slugify":           slugify_filter,
    "linenumbers":       linenumbers_filter,
    "pluralize":         pluralize_filter,
    "yesno":             yesno_filter,
    "default_if_none":   default_if_none_filter,
    "phone2numeric":     phone2numeric_filter,
    "linebreaks":        linebreaks_filter,
    "linebreaksbr":      linebreaksbr_filter,
    "urlize":            urlize_filter,
    "escapejs":          escapejs_filter,
    "json_script":       json_script_filter,
    "filesizeformat":    filesizeformat_filter,
    "floatformat":       floatformat_filter,
}

# These filters produce safe HTML and must be marked as such in Jinja2
_SAFE_FILTERS = {
    "linebreaks", "linebreaksbr", "urlize", "json_script", "linenumbers",
}


def register_builtins(env) -> None:
    """Register all built-in Buraq filters into a Jinja2 environment."""
    for name, fn in _FILTERS.items():
        if name in _SAFE_FILTERS:
            env.filters[name] = fn
        else:
            env.filters[name] = fn
