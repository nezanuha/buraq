# Utility Modules

Buraq ships a collection of utility modules for common tasks.

---

## HTML (`buraq.utils.html`)

```python
from buraq.utils.html import escape, format_html, mark_safe, strip_tags, urlize
```

### SafeString / mark_safe

Mark a string as safe so it won't be double-escaped in templates.

```python
from buraq.utils.html import mark_safe, SafeString

html = mark_safe("<b>Hello</b>")
```

### escape / conditional_escape

```python
escape('<script>alert("xss")</script>')
# → SafeString('&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;')

conditional_escape(already_safe)  # no-op if already SafeString
```

### format_html

Build safe HTML strings — arguments are automatically escaped.

```python
from buraq.utils.html import format_html

link = format_html('<a href="{}">{}</a>', user_url, user_name)
```

### format_html_join

```python
from buraq.utils.html import format_html_join

tags = format_html_join(", ", "<b>{}</b>", ((t,) for t in tag_names))
```

### strip_tags / linebreaks / urlize

```python
strip_tags("<p>Hello <b>World</b></p>")  # → "Hello World"

linebreaks("Hello\n\nWorld")  # → "<p>Hello</p>\n<p>World</p>"

urlize("Visit https://example.com today")
# → 'Visit <a href="https://example.com">https://example.com</a> today'

urlize(text, trim_url_limit=30, nofollow=True)
```

### escapejs

Escape a string for safe use inside JavaScript string literals.

```python
from buraq.utils.html import escapejs

js_value = escapejs(user_input)
# safe to embed as: var x = "{{ value|escapejs }}";
```

---

## Encoding (`buraq.utils.encoding`)

```python
from buraq.utils.encoding import force_str, force_bytes, iri_to_uri
```

| Function | Description |
|---|---|
| `force_str(value)` | Coerce to `str`, decoding bytes |
| `smart_str(value)` | Alias for `force_str` |
| `force_bytes(value)` | Coerce to `bytes`, encoding str |
| `iri_to_uri(iri)` | Percent-encode non-ASCII chars for use in a URI |
| `uri_to_iri(uri)` | Decode percent-encoded sequences to IRI |
| `escape_uri_path(path)` | Percent-encode a path, preserving slashes |

---

## Crypto (`buraq.utils.crypto`)

```python
from buraq.utils.crypto import get_random_string, constant_time_compare, salted_hmac
```

### get_random_string

```python
get_random_string(32)                    # 32-char alphanumeric string
get_random_string(8, allowed_chars="0123456789")  # digits only
```

### constant_time_compare

Compare two strings without leaking timing information — use for HMAC/token verification.

```python
constant_time_compare(expected_token, provided_token)
```

### pbkdf2

```python
from buraq.utils.crypto import pbkdf2

key = pbkdf2("my-password", "random-salt", iterations=1_800_000, dklen=32)
```

### salted_hmac

```python
from buraq.utils.crypto import salted_hmac

mac = salted_hmac("my.key.salt", value_to_sign)
```

---

## Functional (`buraq.utils.functional`)

```python
from buraq.utils.functional import cached_property, SimpleLazyObject, lazy
```

### cached_property

Compute a property once and cache the result on the instance.

```python
class Post:
    @cached_property
    def word_count(self):
        return len(self.body.split())

post = Post()
post.word_count  # computed
post.word_count  # cached — no recompute
```

### SimpleLazyObject

Defer object creation until first access.

```python
from buraq.utils.functional import SimpleLazyObject

current_user = SimpleLazyObject(lambda: get_user_from_session())
str(current_user.username)  # evaluated here
```

### lazy

Create a lazy version of any callable.

```python
from buraq.utils.functional import lazy

lazy_gettext = lazy(gettext, str)
label = lazy_gettext("Hello")
str(label)   # → translated string
```

---

## Date Parsing (`buraq.utils.dateparse`)

Parse ISO 8601 strings without depending on external libraries.

```python
from buraq.utils.dateparse import parse_date, parse_time, parse_datetime, parse_duration

parse_date("2024-03-15")
# → date(2024, 3, 15)

parse_datetime("2024-03-15T10:30:00Z")
# → datetime(2024, 3, 15, 10, 30, tzinfo=UTC)

parse_duration("P1DT2H30M")
# → timedelta(days=1, hours=2, minutes=30)

parse_duration("1 02:30:00")   # simple DD HH:MM:SS format
# → timedelta(days=1, hours=2, minutes=30)

# ISO 8601 week-only periods — P<n>W
parse_duration("P2W")     # → timedelta(weeks=2)
parse_duration("P1.5W")   # → timedelta(weeks=1.5)
parse_duration("-P3W")    # → timedelta(weeks=-3)
```

---

## Module Loading (`buraq.utils.module_loading`)

```python
from buraq.utils.module_loading import import_string, autodiscover_modules
```

### import_string

Load any Python module, class, function, or value by its dotted path — useful for settings-driven pluggability. Top-level modules and submodules are supported directly.

```python
from buraq.utils.module_loading import import_string

Backend = import_string("myapp.backends.LDAPBackend")
backend = Backend()

# Top-level and submodule imports also work
import_string("json")        # returns the json module
import_string("os.path")     # returns the os.path module
```

Raises `ImportError` if the path cannot be resolved.

### autodiscover_modules

Import a named submodule from every app in `INSTALLED_APPS` for side effects — signals, admin registrations, tasks, etc.

```python
from buraq.utils.module_loading import autodiscover_modules

# In AppConfig.ready():
autodiscover_modules("signals", "tasks")
# → imports myapp.signals, otherapp.signals, myapp.tasks, …
```

Modules that don't exist are silently skipped.

---

## Decorators (`buraq.utils.decorators`)

```python
from buraq.utils.decorators import method_decorator
```

### method_decorator

Wrap a **function** decorator so it can be applied to a class-based view method. Handles both sync and async methods correctly.

```python
from buraq.utils.decorators import method_decorator
from buraq.decorators import login_required
from buraq.views.generic import View

class DashboardView(View):
    @method_decorator(login_required)
    async def get(self, request):
        ...
```

Pass `name=` to decorate via the class body (useful when you can't modify the method directly):

```python
@method_decorator(login_required, name="dispatch")
class DashboardView(View):
    ...
```

---

## Data Structures (`buraq.utils.datastructures`)

```python
from buraq.utils.datastructures import MultiValueDict
```

### MultiValueDict

A `dict` subclass that holds multiple values per key — mirrors form data where a single field name can appear more than once (e.g. multi-select checkboxes).

```python
from buraq.utils.datastructures import MultiValueDict

d = MultiValueDict({"colors": ["red", "green", "blue"], "name": ["Alice"]})

d["colors"]             # → "blue"  (last value, like a plain dict)
d.getlist("colors")     # → ["red", "green", "blue"]
d.getfirst("colors")    # → "red"
d.get("missing", "—")   # → "—"

d.appendlist("colors", "yellow")   # ["red", "green", "blue", "yellow"]
d.setlist("colors", ["purple"])    # replace all values

list(d.lists())   # → [("colors", ["purple"]), ("name", ["Alice"])]
```

`MultiValueDict` is returned by `request.form()` when a form posts multiple values for the same field name.

---

## Humanize (`buraq.contrib.humanize`)

```python
from buraq.contrib.humanize import intcomma, ordinal, naturaltime, pluralize
```

| Function | Example | Output |
|---|---|---|
| `intcomma(n)` | `intcomma(1234567)` | `"1,234,567"` |
| `ordinal(n)` | `ordinal(3)` | `"3rd"` |
| `apnumber(n)` | `apnumber(7)` | `"seven"` |
| `pluralize(n)` | `f"item{pluralize(2)}"` | `"items"` |
| `pluralize(n, "match", "matches")` | `pluralize(1, …)` | `"match"` |
| `naturalday(dt)` | today/yesterday/tomorrow | `"yesterday"` |
| `naturaltime(dt)` | relative datetime | `"2 hours ago"` |
| `naturalduration(td)` | timedelta to text | `"1 hour, 30 minutes"` |
| `intword(n)` | `intword(1200000)` | `"1.2 million"` |
