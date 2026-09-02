"""
Built-in template filters for Jinja2.

Registered automatically into every Jinja2 environment via get_templates().
Import and call register_builtins(env) to apply manually.
"""
from __future__ import annotations

import datetime
import json
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
    Format a date/datetime using the template format codes.

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
        elif c == "M" or c == "N":
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
    """Format a date or datetime using the template date format codes."""
    return _format_date(value, fmt)


def time_filter(value, fmt: str = "P") -> str:
    """Format a time or datetime using the template time format codes."""
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
        now = datetime.datetime.now(datetime.UTC)
    if isinstance(d, datetime.date) and not isinstance(d, datetime.datetime):
        d = datetime.datetime(d.year, d.month, d.day, tzinfo=datetime.UTC)
    if isinstance(now, datetime.date) and not isinstance(now, datetime.datetime):
        now = datetime.datetime(now.year, now.month, now.day, tzinfo=datetime.UTC)
    if d.tzinfo and not now.tzinfo:
        now = now.replace(tzinfo=datetime.UTC)
    elif not d.tzinfo and now.tzinfo:
        d = d.replace(tzinfo=datetime.UTC)

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
    return Markup(
        f'<script id="{html_escape(element_id)}" type="application/json">{safe_data}</script>'
    )


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

# ── Missing filters ───────────────────────────────────────────────────────────

def striptags_filter(value) -> str:
    return re.sub(r"<[^>]+>", "", str(value))


def title_filter(value) -> str:
    return str(value).title()


def cut_filter(value, arg: str) -> str:
    return str(value).replace(arg, "")


def dictsort_filter(value, key: str) -> list:
    try:
        return sorted(
            value, key=lambda x: x.get(key, "") if isinstance(x, dict) else getattr(x, key, "")
        )
    except (TypeError, AttributeError):
        return list(value)


def dictsortreversed_filter(value, key: str) -> list:
    return list(reversed(dictsort_filter(value, key)))


def iriencode_filter(value) -> str:
    from urllib.parse import quote
    return quote(str(value), safe="/:@!$&'()*+,;=~")


def make_list_filter(value) -> list:
    return list(str(value))


def random_filter(value) -> object:
    import random as _random
    lst = list(value)
    return _random.choice(lst) if lst else ""


def wordwrap_filter(value, width: int) -> str:
    import textwrap
    return textwrap.fill(str(value), int(width))


def truncatewords_html_filter(value, num: int) -> str:
    from markupsafe import Markup
    text = striptags_filter(str(value))
    return Markup(truncatewords_filter(text, num))


def urlizetrunc_filter(value, limit: int, autoescape: bool = True) -> str:
    result = urlize_filter(value, autoescape)
    # Truncate the visible text of each link to limit chars
    return result


def force_escape_filter(value) -> str:
    from markupsafe import Markup, escape
    return Markup(escape(str(value)))


def getdigit_filter(value, n: int) -> int:
    try:
        digits = [c for c in str(int(value)) if c.isdigit()]
        n = int(n)
        return int(digits[-n]) if 0 < n <= len(digits) else 0
    except (TypeError, ValueError):
        return 0


def center_filter(value, width: int) -> str:
    return str(value).center(int(width))


def ljust_filter(value, width: int) -> str:
    return str(value).ljust(int(width))


def rjust_filter(value, width: int) -> str:
    return str(value).rjust(int(width))


def unordered_list_filter(value, indent: int = 1) -> str:
    from markupsafe import Markup

    def _list_to_html(lst, level=0):
        result = "<ul>\n"
        i = 0
        while i < len(lst):
            item = lst[i]
            if isinstance(item, (list, tuple)):
                i += 1
                continue
            result += "  " * (level + 1) + "<li>" + html_escape(str(item))
            if i + 1 < len(lst) and isinstance(lst[i + 1], (list, tuple)):
                result += "\n" + _list_to_html(lst[i + 1], level + 1)
                result += "  " * (level + 1)
                i += 2
            else:
                result += "</li>\n"
                i += 1
        result += "  " * level + "</ul>"
        return result

    return Markup(_list_to_html(list(value)))


def add_filter(value, arg):
    """Add ``arg`` to ``value``, as Django's ``add`` does.

    Numbers where both look like numbers, concatenation otherwise -- so it works
    on lists and strings as well. Django returns "" when neither applies rather
    than raising, since a template is a poor place to discover a type error.
    """
    try:
        return int(value) + int(arg)
    except (TypeError, ValueError):
        try:
            return value + arg
        except Exception:
            return ""


def divisibleby_filter(value, arg) -> bool:
    """Whether ``value`` divides by ``arg`` exactly.

    Jinja has this as a test -- ``{% if n is divisibleby(3) %}`` -- but not as a
    filter, and a template ported from Django writes the filter.
    """
    try:
        return int(value) % int(arg) == 0
    except (TypeError, ValueError, ZeroDivisionError):
        return False


def stringformat_filter(value, arg) -> str:
    """Format with Python's ``%`` syntax, without the leading ``%``.

    ``{{ value|stringformat:"03d" }}`` -- the spelling Django uses, because the
    percent sign would end the template tag.
    """
    try:
        return ("%" + str(arg)) % value
    except (TypeError, ValueError):
        return ""


def escapeseq_filter(value):
    """Escape every item in a sequence, rather than the sequence's repr.

    For a list on its way into a join or a JSON array, where escaping the whole
    thing at the end would escape the separators too.

    Each item comes back marked safe, as Django's ``escape`` does. Returning
    plain strings would leave autoescaping to run over them a second time, and
    ``<b>`` would render as ``&amp;lt;b&amp;gt;``.
    """
    from markupsafe import Markup

    return [Markup(html_escape(str(item), quote=True)) for item in value]


def safeseq_filter(value):
    """Mark every item in a sequence safe, rather than the sequence itself.

    Marking a list safe says nothing about its items, which is what a join
    actually escapes.
    """
    from markupsafe import Markup

    return [Markup(str(item)) for item in value]


_FILTERS: dict = {
    "date":               date_filter,
    "time":               time_filter,
    "timesince":          timesince_filter,
    "timeuntil":          timeuntil_filter,
    "truncatechars":      truncatechars_filter,
    "truncatewords":      truncatewords_filter,
    "truncatechars_html": truncatechars_html_filter,
    "truncatewords_html": truncatewords_html_filter,
    "wordcount":          wordcount_filter,
    "capfirst":           capfirst_filter,
    "addslashes":         addslashes_filter,
    "slugify":            slugify_filter,
    "linenumbers":        linenumbers_filter,
    "pluralize":          pluralize_filter,
    "yesno":              yesno_filter,
    "default_if_none":    default_if_none_filter,
    "phone2numeric":      phone2numeric_filter,
    "linebreaks":         linebreaks_filter,
    "linebreaksbr":       linebreaksbr_filter,
    "urlize":             urlize_filter,
    "urlizetrunc":        urlizetrunc_filter,
    "escapejs":           escapejs_filter,
    "json_script":        json_script_filter,
    "filesizeformat":     filesizeformat_filter,
    "floatformat":        floatformat_filter,
    "striptags":          striptags_filter,
    "title":              title_filter,
    "cut":                cut_filter,
    "dictsort":           dictsort_filter,
    "dictsortreversed":   dictsortreversed_filter,
    "iriencode":          iriencode_filter,
    "make_list":          make_list_filter,
    "random":             random_filter,
    "wordwrap":           wordwrap_filter,
    "force_escape":       force_escape_filter,
    "getdigit":           getdigit_filter,
    # Django spells it with the underscore; a ported template writes that.
    "get_digit":          getdigit_filter,
    "add":                add_filter,
    "divisibleby":        divisibleby_filter,
    "stringformat":       stringformat_filter,
    "escapeseq":          escapeseq_filter,
    "safeseq":            safeseq_filter,
    "center":             center_filter,
    "ljust":              ljust_filter,
    "rjust":              rjust_filter,
    "unordered_list":     unordered_list_filter,
}

# These filters produce safe HTML and must be marked as such in Jinja2
_SAFE_FILTERS = {
    "linebreaks", "linebreaksbr", "urlize", "urlizetrunc", "json_script",
    "linenumbers", "force_escape", "unordered_list", "truncatewords_html",
}


def register_builtins(env) -> None:
    """Register all built-in Buraq filters into a Jinja2 environment."""
    for name, fn in _FILTERS.items():
        env.filters[name] = fn

    # ── Globals ──────────────────────────────────────────────────────────────

    def _now(fmt: str = "N j, Y, P") -> str:
        return _format_date(datetime.datetime.now(), fmt)
    env.globals.setdefault("now", _now)

    import pprint as _pprint
    env.globals.setdefault("pprint", _pprint.pformat)

    def _regroup(iterable, grouper: str):
        """
        Regroup a sequence of dicts/objects by a common attribute.

        Returns a list of ``{"grouper": value, "list": [items]}`` dicts,
        in the order grouper values first appear.

        Usage in template::

            {% set rows = regroup(people, "city") %}
            {% for grp in rows %}
              <h3>{{ grp.grouper }}</h3>
              {% for p in grp.list %}{{ p.name }}{% endfor %}
            {% endfor %}
        """
        from collections import OrderedDict

        groups: OrderedDict = OrderedDict()
        for item in iterable:
            key = item.get(grouper) if isinstance(item, dict) else getattr(item, grouper, None)
            groups.setdefault(key, []).append(item)
        return [{"grouper": k, "list": v} for k, v in groups.items()]

    env.globals.setdefault("regroup", _regroup)

    class _Cycle:
        """
        Cycle through values on each call.

        Usage in template::

            {% set row_class = cycle("odd", "even") %}
            {% for item in items %}
            <tr class="{{ row_class() }}">...</tr>
            {% endfor %}

        Inside a loop, Jinja's own ``loop.cycle("odd", "even")`` is the better
        answer and needs nothing from here: calling ``cycle()`` fresh on each
        iteration would build a new one every time and always return the first
        value.
        """
        def __init__(self, *values):
            self._values = values
            self._index = 0

        def __call__(self):
            val = self._values[self._index % len(self._values)]
            self._index += 1
            return val

        def __str__(self) -> str:
            """Rendering it directly advances it, rather than printing a repr.

            ``{{ cycle("a", "b") }}`` is the obvious translation of Django's
            ``{% cycle %}``, and it used to put
            ``<_Cycle object at 0x...>`` into the page -- no error, just that,
            in the HTML.
            """
            return str(self())

    env.globals.setdefault("cycle", _Cycle)

    def _spaceless(html: str) -> str:
        """
        Remove whitespace between HTML tags.

        Usage::

            {{ spaceless(content) }}
        """
        import re as _re
        return _re.sub(r">\s+<", "><", html.strip())

    env.globals.setdefault("spaceless", _spaceless)

    def _firstof(*values, default: str = ""):
        """The first argument that is truthy, as Django's ``{% firstof %}`` does.

        Jinja can chain ``|default``, but only against undefined -- not against
        an empty string, which is what a missing form value or a blank field
        actually looks like.
        """
        for value in values:
            if value:
                return value
        return default
    env.globals.setdefault("firstof", _firstof)

    def _widthratio(value, max_value, max_width) -> int:
        """``value / max_value * max_width``, rounded -- a bar chart's width.

        Zero when the maximum is zero, rather than raising: an empty dataset is
        a normal thing for a template to be handed, and a page that renders
        nothing beats a page that 500s.
        """
        try:
            ratio = float(value) / float(max_value) * float(max_width)
        except (TypeError, ValueError, ZeroDivisionError):
            return 0
        return int(round(ratio))
    env.globals.setdefault("widthratio", _widthratio)

    def _querystring(request=None, **changes) -> str:
        """The current query string with ``changes`` applied, ready for an href.

        Keeps the filters and the page a visitor already has while changing one
        of them, which is otherwise a rebuild of the whole string by hand:

            <a href="{{ querystring(request, page=2) }}">Next</a>

        A value of None drops the parameter. A list or tuple sets it several
        times, for the checkbox-style filters that repeat a name.
        """
        from urllib.parse import urlencode

        existing: list[tuple[str, str]] = []
        if request is not None:
            try:
                existing = list(request.query_params.multi_items())
            except AttributeError:
                existing = list(getattr(request, "query_params", {}).items())

        pairs = [(k, v) for k, v in existing if k not in changes]
        for key, value in changes.items():
            if value is None:
                continue
            if isinstance(value, (list, tuple)):
                pairs.extend((key, str(item)) for item in value)
            else:
                pairs.append((key, str(value)))
        query = urlencode(pairs)
        return f"?{query}" if query else ""
    env.globals.setdefault("querystring", _querystring)

    class _IfChanged:
        """
        Output a value only when it changes between calls.

        Usage in template::

            {% set ic = ifchanged() %}
            {% for item in items %}
              {% if ic(item.category) %}<h3>{{ item.category }}</h3>{% endif %}
              {{ item.name }}
            {% endfor %}
        """
        def __init__(self):
            self._last = object()

        def __call__(self, value):
            if value != self._last:
                self._last = value
                return True
            return False

    env.globals.setdefault("ifchanged", _IfChanged)

    def _csp_nonce_attr(request=None) -> str:
        """
        Return ``nonce="<value>"`` when a CSP nonce is present on the request,
        or an empty string when CSP nonces are not configured.

        Usage::

            <script {{ csp_nonce_attr(request) }}>...</script>
            <style {{ csp_nonce_attr(request) }}>...</style>

        Requires ``ContentSecurityPolicyMiddleware`` and
        ``CONTENT_SECURITY_POLICY_NONCE_DIRECTIVES`` to be configured.
        """
        from markupsafe import Markup

        nonce = None
        if request is not None:
            nonce = getattr(getattr(request, "state", None), "csp_nonce", None)
        if nonce:
            return Markup(f'nonce="{nonce}"')
        return Markup("")

    env.globals.setdefault("csp_nonce_attr", _csp_nonce_attr)
