# Templates

## Configuration

```python title="config/settings.py"
TEMPLATES_DIR = str(BASE_DIR / "templates")
```

## Rendering

```python
from buraq.shortcuts import render

async def my_view(request):
    return render(request, "posts/list.html", {"posts": posts})
```

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

## Template globals

Available in every template automatically:

| Name | Value |
|---|---|
| `request` | Current request object |
| `url_for(name, **params)` | Generate URLs by route name |
| `get_messages(request)` | Flash messages |

## Jinja2 features

```html+jinja
{# Comments #}

{# Variables #}
{{ post.title }}
{{ post.title | upper }}
{{ post.created_at.strftime("%Y-%m-%d") }}

{# Control flow #}
{% if post.is_published %}Published{% else %}Draft{% endif %}

{% for post in posts %}
  {{ loop.index }}. {{ post.title }}
{% else %}
  No posts.
{% endfor %}

{# Include #}
{% include "partials/nav.html" %}

{# Macros (reusable snippets) #}
{% macro render_field(field) %}
  <div class="field">
    <label>{{ field.label }}</label>
    <input name="{{ field.html_name }}" value="{{ field.value }}">
  </div>
{% endmacro %}

{{ render_field(form.title) }}
```

## Auto-escaping

Jinja2 auto-escapes HTML by default. To render raw HTML:

```html+jinja
{{ post.content | safe }}
```
