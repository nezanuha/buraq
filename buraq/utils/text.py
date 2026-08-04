"""
buraq.utils.text — string utilities.

Usage::

    from buraq.utils.text import slugify, truncatechars, truncatewords
"""
from __future__ import annotations

import html
import re
import textwrap
import unicodedata
from html.parser import HTMLParser

# ── slugify ───────────────────────────────────────────────────────────────────

def slugify(value: str, allow_unicode: bool = False) -> str:
    """
    Convert *value* to a URL-friendly slug.

    - Lowercases the string
    - Removes characters that aren't alphanumerics, underscores, or hyphens
    - Converts spaces and repeated dashes to single dashes
    - Strips leading and trailing whitespace, dashes, and underscores

    With ``allow_unicode=True`` keeps Unicode letters and numbers instead of
    converting them to ASCII.

    >>> slugify("Hello, World!")
    'hello-world'
    >>> slugify("  Ünïcödé  ", allow_unicode=True)
    'ünïcödé'
    """
    value = str(value).strip()
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
        value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE).strip().lower()
    else:
        value = unicodedata.normalize("NFKD", value)
        value = value.encode("ascii", "ignore").decode("ascii")
        value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "-", value).strip("-_")


# ── truncation ────────────────────────────────────────────────────────────────

def truncatechars(value: str, num: int, truncate: str = "…") -> str:
    """
    Truncate *value* to at most *num* characters, appending *truncate* if cut.

    >>> truncatechars("Hello world", 7)
    'Hello w…'
    >>> truncatechars("Hi", 10)
    'Hi'
    """
    value = str(value)
    if len(value) <= num:
        return value
    return value[: num - len(truncate)] + truncate


def truncatewords(value: str, num: int, truncate: str = "…") -> str:
    """
    Truncate *value* to at most *num* words, appending *truncate* if cut.

    >>> truncatewords("one two three four", 2)
    'one two…'
    """
    words = str(value).split()
    if len(words) <= num:
        return value
    return " ".join(words[:num]) + truncate


def truncatechars_html(value: str, num: int, truncate: str = "…") -> str:
    """
    Truncate *value* to at most *num* characters (excluding HTML tags),
    appending *truncate* if cut.  Properly closes any open HTML tags.

    >>> truncatechars_html("<p>Hello <b>world</b></p>", 7)
    '<p>Hello <b>w…</b></p>'
    """
    return _truncate_html(value, num, truncate, by="chars")


def truncatewords_html(value: str, num: int, truncate: str = "…") -> str:
    """
    Truncate *value* to at most *num* words (excluding HTML tags),
    appending *truncate* if cut.  Properly closes any open HTML tags.

    >>> truncatewords_html("<p>Hello <b>world</b></p>", 1)
    '<p>Hello…</p>'
    """
    return _truncate_html(value, num, truncate, by="words")


# ── capfirst ──────────────────────────────────────────────────────────────────

def capfirst(value: str) -> str:
    """
    Capitalize only the first character of *value*, leaving the rest unchanged.

    >>> capfirst("hello WORLD")
    'Hello WORLD'
    """
    value = str(value)
    return value[:1].upper() + value[1:]


# ── camel_case_to_spaces ──────────────────────────────────────────────────────

def camel_case_to_spaces(value: str) -> str:
    """
    Convert a CamelCase string to lowercase words separated by spaces.

    >>> camel_case_to_spaces("CamelCaseString")
    'camel case string'
    >>> camel_case_to_spaces("HTTPSResponse")
    'h t t p s response'
    """
    return re.sub(r"([A-Z])", r" \1", value).strip().lower()


# ── get_valid_filename ────────────────────────────────────────────────────────

def get_valid_filename(name: str) -> str:
    """
    Return a filename-safe version of *name*.

    Removes path separators and characters that are illegal in filenames on
    Windows and POSIX systems.  Spaces become underscores.

    >>> get_valid_filename("my file (copy).txt")
    'my_file_copy.txt'
    """
    name = str(name).strip().replace(" ", "_")
    # Remove anything that isn't alphanumeric, dash, underscore, or dot
    name = re.sub(r"[^\w.\-]", "", name)
    # Collapse repeated dots (avoid hidden files / extension confusion)
    name = re.sub(r"\.{2,}", ".", name)
    return name.strip("._")


# ── smart_split ───────────────────────────────────────────────────────────────

_SMART_SPLIT_RE = re.compile(
    r"""
    ((?:
        [^\s'"]*
        (?:
            (?:"(?:[^"\\]|\\.)*" | '(?:[^'\\]|\\.)*')   # quoted token
            [^\s'"]*
        )+
    ) | \S+)
    """,
    re.VERBOSE,
)


def smart_split(text: str):
    r"""
    Generator that splits *text* into tokens while preserving quoted strings.

    Useful for parsing template-tag-style argument strings.

    >>> list(smart_split('This is "a test"'))
    ['This', 'is', '"a test"']
    >>> list(smart_split("another 'split' test"))
    ['another', "'split'", 'test']
    """
    for match in _SMART_SPLIT_RE.finditer(text):
        yield match.group(0)


# ── wrap ──────────────────────────────────────────────────────────────────────

def wrap(text: str, width: int) -> str:
    """
    Word-wrap *text* so that each line is at most *width* characters.
    Existing newlines are preserved.

    >>> wrap("The quick brown fox jumps over the lazy dog", 15)
    'The quick brown\\nfox jumps over\\nthe lazy dog'
    """
    lines = []
    for line in str(text).splitlines():
        if line:
            lines.extend(textwrap.wrap(line, width=width) or [line])
        else:
            lines.append("")
    return "\n".join(lines)


# ── unescape_entities ─────────────────────────────────────────────────────────

def unescape_entities(text: str) -> str:
    """
    Convert HTML entities to their corresponding characters.

    >>> unescape_entities("&lt;p&gt;Hello &amp; world&lt;/p&gt;")
    '<p>Hello & world</p>'
    >>> unescape_entities("&#169; 2026")
    '© 2026'
    """
    return html.unescape(str(text))


# ── HTML truncation internals ─────────────────────────────────────────────────

_VOID_ELEMENTS = frozenset([
    "area", "base", "br", "col", "embed", "hr", "img",
    "input", "link", "meta", "param", "source", "track", "wbr",
])


class _TruncateHTMLParser(HTMLParser):
    """SAX-style parser that rebuilds HTML up to a char/word limit."""

    def __init__(self, limit: int, truncate: str, by: str):
        super().__init__(convert_charrefs=False)
        self.limit   = limit
        self.truncate = truncate
        self.by      = by          # "chars" or "words"
        self.output: list[str] = []
        self._open_tags: list[str] = []
        self._count  = 0           # chars or words consumed
        self._done   = False

    # ── internal counter ──────────────────────────────────────────────────────

    def _add_text(self, data: str) -> None:
        if self._done:
            return
        if self.by == "chars":
            remaining = self.limit - self._count
            if len(data) > remaining:
                self.output.append(data[:remaining] + self.truncate)
                self._count += remaining
                self._done = True
            else:
                self.output.append(data)
                self._count += len(data)
        else:  # words
            words = data.split()
            remaining = self.limit - self._count
            if len(words) > remaining:
                self.output.append(" ".join(words[:remaining]) + self.truncate)
                self._count += remaining
                self._done = True
            else:
                # Preserve original spacing
                self.output.append(data)
                self._count += len(words)

    # ── HTMLParser callbacks ──────────────────────────────────────────────────

    def handle_starttag(self, tag: str, attrs):
        if self._done:
            return
        attr_str = ""
        for name, val in attrs:
            if val is None:
                attr_str += f" {name}"
            else:
                attr_str += f' {name}="{html.escape(val, quote=True)}"'
        self.output.append(f"<{tag}{attr_str}>")
        if tag.lower() not in _VOID_ELEMENTS:
            self._open_tags.append(tag)

    def handle_endtag(self, tag: str):
        if self._done:
            return
        self.output.append(f"</{tag}>")
        if tag in self._open_tags:
            self._open_tags.remove(tag)

    def handle_data(self, data: str):
        self._add_text(data)

    def handle_entityref(self, name: str):
        self._add_text(f"&{name};")

    def handle_charref(self, name: str):
        self._add_text(f"&#{name};")

    def close_open_tags(self) -> str:
        """Return closing tags for any still-open elements."""
        return "".join(f"</{tag}>" for tag in reversed(self._open_tags))


def _truncate_html(value: str, limit: int, truncate: str, by: str) -> str:
    parser = _TruncateHTMLParser(limit, truncate, by)
    parser.feed(str(value))
    parser.close()
    return "".join(parser.output) + parser.close_open_tags()
