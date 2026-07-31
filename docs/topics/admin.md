# Admin Panel

Buraq includes an admin panel powered by [SQLAdmin](https://aminalaee.dev/sqladmin/).

## Setup

```python title="config/urls.py"
from buraq import Buraq
from buraq.contrib.admin import BuraqAdmin

app   = Buraq(settings_module="config.settings")
admin = BuraqAdmin(app)
```

Visit `/admin` — the panel is live.

## Registering models

```python title="posts/admin.py"
from buraq.contrib.admin import ModelAdmin
from posts.models import Post, Comment


class PostAdmin(ModelAdmin, model=Post):
    column_list          = [Post.id, Post.title, Post.is_published, Post.created_at]
    column_searchable_list = [Post.title, Post.slug]
    column_sortable_list   = [Post.id, Post.created_at]
    column_filters         = [Post.is_published]
    can_create             = True
    can_edit               = True
    can_delete             = True


class CommentAdmin(ModelAdmin, model=Comment):
    column_list = [Comment.id, Comment.author_name, Comment.created_at]
```

Then register in your app startup:

```python title="config/urls.py"
from posts.admin import PostAdmin, CommentAdmin

admin = BuraqAdmin(app)
admin.add_view(PostAdmin)
admin.add_view(CommentAdmin)
```

## Requires sqladmin

```bash
uv add sqladmin
```

`sqladmin` is an optional dependency — Buraq will raise a clear error at startup if you use `BuraqAdmin` without it installed.
