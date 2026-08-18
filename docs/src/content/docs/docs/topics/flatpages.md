---
title: "Flatpages"
description: "buraq.contrib.flatpages provides simple database-backed static pages — useful for About, Privacy Policy, Terms of Service pages that need occasional editing…"
---

`buraq.contrib.flatpages` provides simple database-backed static pages — useful for About, Privacy Policy, Terms of Service pages that need occasional editing without redeployment.

## Setup

```python
INSTALLED_APPS = ["buraq.contrib.flatpages", ...]
```

Run migrations to create the `flatpages_flatpage` table.

## Creating a flat page

```python
from buraq.contrib.flatpages.models import FlatPage

page = await FlatPage.objects.create(
    url="/about",
    title="About Us",
    content="<h1>About</h1><p>We build great software.</p>",
)
```

## Serving flat pages

Wire the view in your URL config:

```python
from buraq.contrib.flatpages.views import flatpage

urlpatterns = [
    path("/about", flatpage),
    path("/privacy", flatpage),
]
```

The view reads `url` from `request.url.path` and raises `Http404` if no matching page exists.

## Custom templates

Set `template_name` on a `FlatPage` to use a custom template:

```python
page.template_name = "pages/about.html"
await page.save()
```

The template receives `{{ flatpage }}` with all model attributes. If `template_name` is empty, `flatpages/default.html` is used.

## FlatPage fields

| Field | Type | Description |
|---|---|---|
| `url` | `String(255)` | URL path, e.g. `/about` (unique) |
| `title` | `String(255)` | Page title |
| `content` | `Text` | HTML content |
| `template_name` | `String(255)` | Optional custom template |
| `enable_comments` | `Boolean` | Whether comments are enabled |
| `registration_required` | `Boolean` | Restrict to authenticated users |
