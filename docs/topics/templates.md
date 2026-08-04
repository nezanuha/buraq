# Templates

Buraq uses Jinja2 as its sole template engine.

---

## Configuration

```python title="config/settings.py"
TEMPLATES_DIR = str(BASE_DIR / "templates")
```

---

## Rendering

```python
from buraq.shortcuts import render

async def my_view(request):
    return render(request, "posts/list.html", {"posts": posts})
```

---

## Jinja2 vs Django template syntax

Jinja2 and Django templates share similar syntax (`{{ var }}`, `{% block %}`, `{% for %}`, `{% if %}`) but they are not identical:

| Feature | Jinja2 (Buraq) | Django templates |
|---|---|---|
| Filters | `{{ val\|upper }}` | `{{ val\|upper }}` — same |
| Tests | `{% if x is defined %}` | not available |
| Macros | `{% macro foo() %}` | not available |
| Expressions | `{{ 1 + 2 }}`, `{{ loop.index }}` | limited |
| `{% set %}` | ✅ | ✅ |
| `{% include %}` | ✅ | ✅ |
| `{% extends %}` / `{% block %}` | ✅ | ✅ |
| `{% with %}` | ✅ | ✅ |
| Custom globals | `@register.global` in `templatetags.py` | `@register.simple_tag` + `{% load %}` |
| Custom filters | `@register.filter` in `templatetags.py` | `@register.filter` + `{% load %}` |
| Custom tests | `@register.test` in `templatetags.py` | not available |
| `{% load %}` | ❌ not needed — tags auto-discovered at startup | required in every template |
| CSRF token | `{{ csrf_input }}` | `{% csrf_token %}` |

Buraq registers its own globals (`_()`, `get_language()`, `reverse()`, etc.) to cover the most common cases without any extra setup.

---

## CSRF token — {{ csrf_input }}

Buraq uses `{{ csrf_input }}` — a plain string global — instead of a special `{% csrf_token %}` tag.

=== "Buraq"

    ```html+jinja
    <form method="post">
      {{ csrf_input }}
      ...
    </form>
    ```

=== "Django equivalent"

    ```html+jinja
    <form method="post">
      {% csrf_token %}
      ...
    </form>
    ```

**Why `{{ csrf_input }}` is better:**

- **Consistent** — `{{ }}` outputs values, `{% %}` is for control flow. A CSRF token is a value, so `{{ }}` is the right syntax. Using `{% csrf_token %}` breaks this convention by making a tag output HTML.
- **Simple mental model** — `csrf_input` is just a string injected into `env.globals` at startup, the same mechanism as every other global. Nothing special about it.
- **Composable** — because it's a plain value, it works anywhere a value is valid:

    ```html+jinja
    {# inline in a form #}
    {{ csrf_input }}

    {# stored in a variable for reuse #}
    {% set token = csrf_input %}
    ```

---

## Why no {% load %}?

=== "Buraq"

    ```python title="myapp/templatetags.py"
    from buraq.template import register

    @register.global
    def my_tag():
        return "hello"
    ```

    ```html+jinja title="any template — just works"
    {{ my_tag() }}
    ```

=== "Django equivalent"

    ```python title="myapp/templatetags/myapp_tags.py"
    from django import template

    register = template.Library()

    @register.simple_tag
    def my_tag():
        return "hello"
    ```

    ```html+jinja title="every template that uses it"
    {% load myapp_tags %}
    {% my_tag %}
    ```

**Why Buraq wins:**

- **Simpler** — 1 file, 1 decorator, no `{% load %}` ever; Django requires a separate `templatetags/` directory, `__init__.py`, a `Library()` instance, the decorator, and `{% load %}` in every template that uses it
- **Safer** — tag errors are caught at startup, not silently at render time when a template forgets `{% load %}`
- **Faster** — no `{% load %}` parsing on every request; all tags registered once into `env.globals` at startup
- **More powerful** — `@register.global` gives you a full callable with arguments (`{{ fn(a, b) }}`); `simple_tag` has limitations around argument handling and can't be called with keyword args as naturally in template syntax

Buraq auto-discovers `templatetags.py` in every `INSTALLED_APPS` app at startup and registers all globals, filters, and tests into the Jinja2 environment once. This means:

- **No per-template `{% load %}`** — no parsing overhead on every request
- **One file, one decorator** — vs Django's `templatetags/` directory, `__init__.py`, `Library()` instance, decoration, and `{% load %}` in every template
- **Fail loudly at startup** — a missing or broken tag file is caught immediately, not silently at render time

**Performance** — both resolve to the same Jinja2 `env.globals` / `env.filters` dict lookup at render time, so runtime speed is identical. The difference is startup: Buraq's auto-discovery scans once at app startup and registers everything — no per-template `{% load %}` parsing overhead on every request.

**Maintenance** — one file (`templatetags.py`), one decorator, done. The alternative requires: create `templatetags/` directory, add `__init__.py`, create the tag file, instantiate `Library()`, decorate, then `{% load %}` in every template that uses it. That's 5 steps vs 1. When you rename or move a tag, the other approach breaks silently at render time (missing `{% load %}`); Buraq fails loudly at startup.

**Scalability** — auto-discovery scales better. As the app grows, new `templatetags.py` files in new apps are picked up automatically — no central registration, no config changes. `{% load %}` becomes a maintenance burden across hundreds of templates when tag libraries are reorganized.

See [Template Tags](template-tags.md) for the full API.

---

## Template inheritance

```html+jinja title="templates/base.html"
<!DOCTYPE html>
<html>
<head>
  <title>{% block title %}My Site{% endblock %}</title>
</head>
<body>
  {% block content %}{% endblock %}
</body>
</html>
```

```html+jinja title="templates/posts/list.html"
{% extends "base.html" %}

{% block title %}Posts{% endblock %}

{% block content %}
  {% for post in posts %}
    <h2>{{ post.title }}</h2>
  {% endfor %}
{% endblock %}
```

---

## Built-in template globals

Available in every template automatically — no import or passing from views needed:

| Name | Description |
|---|---|
| `request` | Current request object |
| `get_messages(request)` | Flash messages |
| `_()` / `gettext()` | Translate a string (when `USE_I18N = True`) |
| `ngettext()` | Plural translation |
| `pgettext()` | Context-disambiguated translation |
| `get_language()` | Active language code |
| `get_language_bidi()` | `True` for RTL languages |
| `csrf_input` | Hidden CSRF input field (HTML) |

---

## Jinja2 features

```html+jinja
{# Comments #}

{# Variables and filters #}
{{ post.title }}
{{ post.title|upper }}
{{ post.created_at.strftime("%Y-%m-%d") }}

{# Expressions #}
{{ loop.index }}. {{ post.title }}
{{ 1 + 2 }}

{# Control flow #}
{% if post.is_published %}Published{% else %}Draft{% endif %}

{% for post in posts %}
  {{ loop.index }}. {{ post.title }}
{% else %}
  No posts.
{% endfor %}

{# Tests #}
{% if loop.index is even %}<tr class="alt">{% endif %}
{% if post is defined %}{{ post.title }}{% endif %}

{# Set variables #}
{% set total = items|length %}

{# Include #}
{% include "partials/nav.html" %}

{# Macros — reusable snippets #}
{% macro render_field(field) %}
  <div class="field">
    <label>{{ field.label }}</label>
    <input name="{{ field.html_name }}" value="{{ field.value }}">
  </div>
{% endmacro %}

{{ render_field(form.title) }}
```

---

## Auto-escaping

Jinja2 auto-escapes HTML output by default. To render trusted HTML, use the `safe` filter or mark your function with `is_safe=True` in the tag registry:

```html+jinja
{{ post.content|safe }}
```
