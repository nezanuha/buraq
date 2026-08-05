"""
HTML utilities — escaping, safe strings, formatting.

Usage:
    from buraq.utils.html import escape, format_html, mark_safe, strip_tags
"""
from __future__ import annotations

import re
from html import escape as _html_escape
from html.parser import HTMLParser


class SafeString(str):
    """A str subclass that is marked safe to render without further escaping."""

    def __add__(self, other):
        result = super().__add__(other)
        if isinstance(other, SafeString):
            return SafeString(result)
        return result

    def __radd__(self, other):
        result = str.__add__(other, self)
        if isinstance(other, SafeString):
            return SafeString(result)
        return result


def mark_safe(value: str) -> SafeString:
    """Mark a string as safe HTML — will not be escaped in templates."""
    return SafeString(value)


def escape(value: str) -> SafeString:
    """
    HTML-escape a string and return a SafeString.

    Replaces &, <, >, ", ' with their HTML entity equivalents.
    """
    return SafeString(_html_escape(str(value), quote=True))


def escapejs(value: str) -> SafeString:
    """
    Escape a string for use inside a JavaScript string literal.

    Replaces backslash, single/double quotes, newlines, and other
    control characters with safe escape sequences.
    """
    _JS_ESCAPES = {
        ord("\\"): "\\\\",
        ord("\""): "\\\"",
        ord("'"): "\\'",
        ord("\n"): "\\n",
        ord("\r"): "\\r",
        ord("\t"): "\\t",
        ord("\x0b"): "\\x0b",
        ord("\x0c"): "\\f",
        ord("\x00"): "\\u0000",
        ord(""): "\\u2028",
        ord(""): "\\u2029",
    }
    return SafeString(str(value).translate(_JS_ESCAPES))


def conditional_escape(value) -> SafeString:
    """Escape value only if it is not already a SafeString."""
    if isinstance(value, SafeString):
        return value
    return escape(str(value))


def format_html(format_string: str, *args, **kwargs) -> SafeString:
    """
    Format a string with HTML-escaped arguments, returning a SafeString.

    Use this instead of str.format() when building HTML to avoid XSS:

        html = format_html('<a href="{}">{}</a>', url, label)
    """
    safe_args = [conditional_escape(a) for a in args]
    safe_kwargs = {k: conditional_escape(v) for k, v in kwargs.items()}
    return SafeString(format_string.format(*safe_args, **safe_kwargs))


def format_html_join(sep: str, format_string: str, args_generator) -> SafeString:
    """
    Join a sequence of format_html() results with ``sep``.

        format_html_join(", ", "<b>{}</b>", ((name,) for name in names))
    """
    parts = [format_html(format_string, *args) for args in args_generator]
    return SafeString(sep.join(parts))


def linebreaks(value: str) -> SafeString:
    """Convert plain text newlines to HTML <p> and <br> tags."""
    value = escape(value)
    paragraphs = re.split(r"\n{2,}", value)
    result = []
    for para in paragraphs:
        para = para.replace("\n", "<br>")
        result.append(f"<p>{para}</p>")
    return SafeString("\n".join(result))


class _MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return "".join(self.fed)


def strip_tags(value: str) -> str:
    """Remove all HTML tags from a string."""
    stripper = _MLStripper()
    stripper.feed(str(value))
    return stripper.get_data()


_URL_RE = re.compile(
    r"(https?://[^\s<>\"']+|www\.[^\s<>\"']+)",
    re.IGNORECASE,
)


def urlize(value: str, trim_url_limit: int = None, nofollow: bool = False) -> SafeString:
    """Convert URLs in plain text to clickable HTML links."""
    def replace_url(match):
        url = match.group(0)
        href = url if url.startswith("http") else f"http://{url}"
        if trim_url_limit is None or len(url) <= trim_url_limit:
            label = url
        else:
            label = url[:trim_url_limit] + "…"
        rel = ' rel="nofollow"' if nofollow else ""
        return f'<a href="{escape(href)}"{rel}>{escape(label)}</a>'
    return SafeString(_URL_RE.sub(replace_url, escape(value)))


__all__ = [
    "SafeString", "mark_safe", "escape", "escapejs", "conditional_escape",
    "format_html", "format_html_join", "linebreaks", "strip_tags", "urlize",
]
