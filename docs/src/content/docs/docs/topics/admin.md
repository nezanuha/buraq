---
title: "Admin Panel"
description: "Buraq ships with a built-in admin panel — no third-party dependencies required. It provides automatic CRUD pages for every registered model, with search…"
---

Buraq ships with a built-in admin panel — no third-party dependencies required.
It provides automatic CRUD pages for every registered model, with search, pagination,
and dark-themed UI powered by Frutjam CSS.

## Setup

Mount the admin in your URL config, like any other set of URLs:

```python title="config/urls.py"
from buraq.contrib import admin
from buraq.urls import path

urlpatterns = [
    path("/admin", admin.site.urls),
]
```

Log in with any account that has `is_staff = True` or `is_superuser = True`.

:::tip[Move it somewhere less obvious]
`/admin` is the first path a scanner tries. The prefix is whatever you write, and
everything the admin builds follows it — links, redirects, the login page:

```python
path("/secret-door-9f2", admin.site.urls)
```

Leaving the line out altogether is how a deployment ships without an admin.
:::

Create your first admin user from the command line:

```bash
buraq createsuperuser
```

## Registering models

Create an `admin.py` inside your app. The admin panel auto-discovers these files
on startup.

```python title="posts/admin.py"
from buraq.contrib import admin
from posts.models import Category, Comment, Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display  = ["id", "title", "is_published", "created_at"]
    search_fields = ["title", "slug"]
    ordering      = ["-created_at"]
    list_per_page = 25
    readonly_fields = ["created_at"]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["id", "author_name", "post_id", "created_at"]
    search_fields = ["author_name"]


admin.site.register(Category)      # default ModelAdmin — shows all columns
```

The decorator takes several models if one `ModelAdmin` suits them all
(`@admin.register(Post, Draft)`), and `site.register(Model)` on its own is the
way to register a model with the default admin, as `Category` does above.

Importing the module — `from buraq.contrib import admin` — keeps `ModelAdmin`,
`register` and `site` under one name. Importing them directly works the same
way:

```python
from buraq.contrib.admin import ModelAdmin, site

class PostAdmin(ModelAdmin):
    ...

site.register(Post, PostAdmin)
```

## ModelAdmin options

| Option | Default | Description |
|--------|---------|-------------|
| `list_display` | all columns (up to 6) | Columns shown in the list view |
| `search_fields` | `[]` | Fields searched via the search box (case-insensitive LIKE) |
| `list_filter` | `[]` | Field names for sidebar filters *(future)* |
| `ordering` | `["-id"]` | Default sort for list view |
| `list_per_page` | `20` | Rows per page |
| `fields` | all editable columns | Fields shown in add/change forms |
| `readonly_fields` | `[]` | Fields displayed but not editable in forms |
| `can_create` | `True` | Show the **+ Add** button |
| `can_edit` | `True` | Show the **Edit** button per row |
| `can_delete` | `True` | Show the **Delete** button per row |

## AdminSite

`site` is the global `AdminSite` instance shared across your project.
You can also create isolated sites for multi-tenant setups:

```python
from buraq.contrib.admin import AdminSite

private_site = AdminSite()
private_site.site_header = "Staff Panel"
private_site.register(Order, OrderAdmin)

urlpatterns = [
    path("/staff", private_site.urls),
]
```

Two sites can be mounted at once, each at its own prefix, each with its own
registry.

## Authentication

The admin uses a separate signed session cookie (`_buraq_admin`).
Any user with `is_staff=True` or `is_superuser=True` can log in via `/admin/login`.
The cookie is signed with your project's `SECRET_KEY`.

## Production security

:::caution[HTTPS required]
The admin session cookie is set with `Secure=True` when `DEBUG = False`, meaning the
browser will only send it over HTTPS. Always deploy the admin behind HTTPS in production —
never expose it on plain HTTP.
:::

- Set a strong, random `SECRET_KEY` — the admin cookie is HMAC-signed with it.
- Restrict `/admin` to internal networks or a VPN using your reverse proxy; Buraq does not
  ship IP allowlisting for the admin panel.
- The login endpoint enforces the global `RATE_LIMIT` setting (default `100/minute` per IP).
  Tighten this if you expose the admin publicly:

```python title="config/settings.py"
RATE_LIMIT = "10/minute"
```
