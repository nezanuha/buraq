# Text Utilities

`buraq.utils.text` provides string helpers for slugifying, truncating, wrapping, and sanitizing text.

---

## Usage

```python
from buraq.utils.text import (
    slugify,
    truncatechars,
    truncatewords,
    truncatechars_html,
    truncatewords_html,
    capfirst,
    camel_case_to_spaces,
    get_valid_filename,
    smart_split,
    wrap,
    unescape_entities,
)
```

---

## slugify()

Convert a string to a URL-friendly slug.

```python
from buraq.utils.text import slugify

slugify("Hello, World!")          # → "hello-world"
slugify("  Spaces   & symbols!")  # → "spaces-symbols"
slugify("Ünïcödé", allow_unicode=True)  # → "ünïcödé"
```

With `allow_unicode=False` (default) the output contains only ASCII letters, numbers, and hyphens. With `allow_unicode=True` Unicode letters and numbers are kept.

---

## truncatechars()

Truncate to at most *N* characters, appending `…` if cut.

```python
from buraq.utils.text import truncatechars

truncatechars("Hello world", 7)          # → "Hello w…"
truncatechars("Short", 10)               # → "Short"
truncatechars("Hello world", 7, "...")   # → "Hell..."
```

---

## truncatewords()

Truncate to at most *N* words, appending `…` if cut.

```python
from buraq.utils.text import truncatewords

truncatewords("one two three four", 2)   # → "one two…"
truncatewords("one two", 5)              # → "one two"
```

---

## truncatechars_html()

Truncate HTML to at most *N* characters (excluding tags), then close any open tags.

```python
from buraq.utils.text import truncatechars_html

truncatechars_html("<p>Hello <b>world</b></p>", 7)
# → "<p>Hello <b>w…</b></p>"
```

---

## truncatewords_html()

Truncate HTML to at most *N* words (excluding tags), then close any open tags.

```python
from buraq.utils.text import truncatewords_html

truncatewords_html("<p>Hello <b>world</b></p>", 1)
# → "<p>Hello…</p>"
```

---

## capfirst()

Capitalize only the first character, leaving the rest unchanged.

```python
from buraq.utils.text import capfirst

capfirst("hello WORLD")   # → "Hello WORLD"
capfirst("already")       # → "Already"
```

---

## camel_case_to_spaces()

Convert a CamelCase string to lowercase words separated by spaces.

```python
from buraq.utils.text import camel_case_to_spaces

camel_case_to_spaces("CamelCaseString")   # → "camel case string"
camel_case_to_spaces("MyHTTPSView")       # → "my h t t p s view"
```

---

## get_valid_filename()

Sanitize a string for use as a filename. Replaces spaces with underscores and removes characters that are illegal on Windows and POSIX.

```python
from buraq.utils.text import get_valid_filename

get_valid_filename("my file (copy).txt")   # → "my_file_copy.txt"
get_valid_filename("../../etc/passwd")     # → "etcpasswd"
get_valid_filename("résumé.pdf")           # → "résumé.pdf"
```

---

## smart_split()

Split a string into tokens while preserving quoted strings. Useful for parsing argument strings.

```python
from buraq.utils.text import smart_split

list(smart_split('This is "a test"'))
# → ['This', 'is', '"a test"']

list(smart_split("key='some value' other"))
# → ["key='some value'", 'other']
```

---

## wrap()

Word-wrap text so that each line is at most *width* characters. Existing newlines are preserved.

```python
from buraq.utils.text import wrap

wrap("The quick brown fox jumps over the lazy dog", 15)
# → "The quick brown\nfox jumps over\nthe lazy dog"
```

---

## unescape_entities()

Convert HTML entities to their corresponding Unicode characters.

```python
from buraq.utils.text import unescape_entities

unescape_entities("&lt;p&gt;Hello &amp; world&lt;/p&gt;")
# → "<p>Hello & world</p>"

unescape_entities("&#169; 2026")
# → "© 2026"
```
