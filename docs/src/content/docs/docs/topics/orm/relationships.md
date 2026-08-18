---
title: "Relationships"
description: "**DB_* variants are preferred** in async applications. They skip loading related objects into Python memory, making bulk deletes orders of magnitude faster."
---

## ForeignKey (Many-to-One)

```python
class Comment(models.Model):
    post   = models.ForeignKey("Post", on_delete="CASCADE")
    body   = models.TextField()
```

Querying:

```python
# Get all comments for a post
comments = await Comment.objects.filter(post_id=post.id).all()

# Get the post for a comment (access the FK id directly)
comment = await Comment.objects.get(id=1)
post    = await Post.objects.get(id=comment.post_id)
```

## OneToOneField

```python
class Profile(models.Model):
    user   = models.OneToOneField("User", on_delete="CASCADE")
    bio    = models.TextField()
    avatar = models.URLField()
```

## ForeignKey options

```python
models.ForeignKey(
    "Post",
    on_delete  = models.CASCADE,   # see table below
    null       = False,
    db_index   = True,             # adds an index on the FK column (default: True)
)
```

### on_delete constants

| Constant | SQL clause | Notes |
|---|---|---|
| `CASCADE` | `ON DELETE CASCADE` | Python callbacks fire (signals, pre_delete) |
| `DB_CASCADE` | `ON DELETE CASCADE` | Database handles deletion — no Python involved |
| `SET_NULL` | `ON DELETE SET NULL` | Python callbacks fire; requires `null=True` |
| `DB_SET_NULL` | `ON DELETE SET NULL` | Database sets NULL — no Python involved |
| `SET_DEFAULT` | `ON DELETE SET DEFAULT` | Python callbacks fire |
| `DB_SET_DEFAULT` | `ON DELETE SET DEFAULT` | Database sets default — no Python involved |
| `PROTECT` | `ON DELETE RESTRICT` | Raises an error if related rows exist |
| `RESTRICT` | `ON DELETE RESTRICT` | Same as PROTECT |
| `DO_NOTHING` | `ON DELETE NO ACTION` | No enforcement at all |

**`DB_*` variants are preferred** in async applications. They skip loading related objects into Python memory, making bulk deletes orders of magnitude faster.

```python
class Comment(models.Model):
    post = models.ForeignKey("Post", on_delete=models.DB_CASCADE)

class Profile(models.Model):
    user = models.OneToOneField("User", on_delete=models.DB_CASCADE)
```

## Querying across relationships

```python
# Filter comments by post fields (join via filter)
comments = await Comment.objects.filter(post_id__in=[1, 2, 3])

# Get all posts in a category
posts = await Post.objects.filter(category_id=category.id)
```

:::note[No lazy loading]
Buraq does not support lazy loading of related objects (it can't — we're async). Always fetch related objects explicitly with a separate query or use `select_related` (planned).
:::