# Admin Panel

Buraq ships with a built-in admin panel — no third-party dependencies required.
It provides automatic CRUD pages for every registered model, with search, pagination,
and dark-themed UI powered by Frutjam CSS.

## Setup

Mount the admin panel once in your URL config:

```python title="config/urls.py"
from buraq import Buraq
from buraq.contrib.admin import BuraqAdmin

app   = Buraq(settings_module="config.settings")
admin = BuraqAdmin(app)
```

The panel is now available at `/admin`. Log in with any account that has
`is_staff = True` or `is_superuser = True`.

Create your first admin user from the command line:

```bash
buraq createsuperuser
```

## Registering models

Create an `admin.py` inside your app and register models with `site.register()`.
The admin panel auto-discovers these files on startup.

```python title="posts/admin.py"
from buraq.contrib.admin import ModelAdmin, site
from posts.models import Post, Comment


class PostAdmin(ModelAdmin):
    list_display  = ["id", "title", "is_published", "created_at"]
    search_fields = ["title", "slug"]
    ordering      = ["-created_at"]
    list_per_page = 25
    readonly_fields = ["created_at"]


class CommentAdmin(ModelAdmin):
    list_display = ["id", "author_name", "post_id", "created_at"]
    search_fields = ["author_name"]


site.register(Post, PostAdmin)
site.register(Comment, CommentAdmin)
site.register(Category)            # default ModelAdmin — shows all columns
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

BuraqAdmin(app, admin_site=private_site)
```

## Authentication

The admin uses a separate signed session cookie (`_buraq_admin`).
Any user with `is_staff=True` or `is_superuser=True` can log in via `/admin/login`.
The cookie is signed with your project's `SECRET_KEY`.

## Production security

!!! warning "HTTPS required"
    The admin session cookie is set with `Secure=True` when `DEBUG = False`, meaning the
    browser will only send it over HTTPS. Always deploy the admin behind HTTPS in production —
    never expose it on plain HTTP.

- Set a strong, random `SECRET_KEY` — the admin cookie is HMAC-signed with it.
- Restrict `/admin` to internal networks or a VPN using your reverse proxy; Buraq does not
  ship IP allowlisting for the admin panel.
- The login endpoint enforces the global `RATE_LIMIT` setting (default `100/minute` per IP).
  Tighten this if you expose the admin publicly:

```python title="config/settings.py"
RATE_LIMIT = "10/minute"
```
