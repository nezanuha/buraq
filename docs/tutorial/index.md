# Tutorial

This tutorial walks you through building a complete blog application with Buraq — models, views, forms, templates, and authentication.

**What you'll build:** A blog with posts, categories, comments, and user authentication.

## Parts

1. [**Models**](models.md) — Define your data with Buraq ORM
2. [**Views & URLs**](views-urls.md) — Handle requests with FBVs and CBVs
3. [**Forms**](forms.md) — Validate user input with Form and ModelForm
4. [**Templates**](templates.md) — Render HTML with Jinja2
5. [**Authentication**](authentication.md) — Protect views with JWT auth

## Prerequisites

- Python 3.11+
- Buraq installed (see [Installation](../getting-started/installation.md))
- Basic Python and async/await knowledge

## Setup

```bash
buraq startproject buraq_blog
cd buraq_blog
uv sync
python manage.py startapp posts
```

Add `"posts"` to `INSTALLED_APPS` in `config/settings.py`.
