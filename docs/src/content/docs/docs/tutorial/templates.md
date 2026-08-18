---
title: "Part 4 — Templates"
description: "Buraq uses Jinja2 for templating. If you know Django templates, Jinja2 is almost identical with minor syntax differences."
---

Buraq uses **Jinja2** for templating. If you know Django templates, Jinja2 is almost identical with minor syntax differences.

## Setup

```python title="config/settings.py"
TEMPLATES_DIR = str(BASE_DIR / "templates")
```

## Base template

```html+jinja title="templates/base.html"
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{% block title %}My Blog{% endblock %}</title>
  <link rel="stylesheet" href="{{ url_for('static', path='/css/style.css') }}">
</head>
<body>
  <nav>
    <a href="/posts/">Blog</a>
    <a href="/posts/new">New Post</a>
  </nav>

  {% for message in get_messages(request) %}
    <div class="message {{ message.level }}">{{ message.text }}</div>
  {% endfor %}

  <main>
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

## List template

```html+jinja title="templates/posts/list.html"
{% extends "base.html" %}

{% block title %}Posts{% endblock %}

{% block content %}
<h1>Posts</h1>

{% for post in posts %}
  <article>
    <h2><a href="/posts/{{ post.slug }}">{{ post.title }}</a></h2>
    <time>{{ post.created_at.strftime("%B %d, %Y") }}</time>
  </article>
{% else %}
  <p>No posts yet.</p>
{% endfor %}

{% if is_paginated %}
  {% if page_obj.has_previous() %}
    <a href="?page={{ page_obj.previous_page_number() }}">Previous</a>
  {% endif %}
  <span>Page {{ page_obj.number }} of {{ paginator.num_pages }}</span>
  {% if page_obj.has_next() %}
    <a href="?page={{ page_obj.next_page_number() }}">Next</a>
  {% endif %}
{% endif %}
{% endblock %}
```

## Rendering from a view

```python
from buraq.shortcuts import render

async def post_list(request):
    posts = await Post.objects.filter(is_published=True)
    return await render(request, "posts/list.html", {"posts": posts})
```

## Template globals

These are available in every template without passing them explicitly:

| Variable | Description |
|---|---|
| `request` | The current request object |
| `url_for(name, **params)` | Generate a URL by route name |
| `get_messages(request)` | Flash messages for the current request |

## Jinja2 vs Django templates

| Feature | Django | Jinja2 (Buraq) |
|---|---|---|
| Variable | `{{ var }}` | `{{ var }}` |
| Block | `{% block %}` | `{% block %}` |
| Extends | `{% extends %}` | `{% extends %}` |
| For loop | `{% for %}{% endfor %}` | `{% for %}{% endfor %}` |
| If | `{% if %}{% endif %}` | `{% if %}{% endif %}` |
| Filter | `{{ var\|lower }}` | `{{ var\|lower }}` |
| Function call | `{% url 'name' %}` | `{{ url_for('name') }}` |
| Comments | `{# comment #}` | `{# comment #}` |

Next: [Authentication →](authentication.md)
