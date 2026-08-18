---
title: "Part 1 — Models"
description: "Models are Python classes that map to database tables. Define them once — Buraq handles the SQL."
---

Models are Python classes that map to database tables. Define them once — Buraq handles the SQL.

## Define your models

```python title="posts/models.py"
from buraq import models
from buraq.signals import post_save


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        table_name = "categories"


class Post(models.Model):
    title        = models.CharField(max_length=200)
    slug         = models.SlugField(max_length=200, unique=True)
    content      = models.TextField()
    category     = models.ForeignKey("Category", on_delete="SET NULL", nullable=True)
    is_published = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)


class Comment(models.Model):
    post        = models.ForeignKey("Post", on_delete="CASCADE")
    author_name = models.CharField(max_length=100)
    body        = models.TextField()
    created_at  = models.DateTimeField(auto_now_add=True)
```

## Create the tables

```bash
buraq migrate
```

:::note
Buraq uses Alembic for migrations. `migrate` with no pending migrations runs a simple `create_all` for new tables.
:::

## Using the ORM

All ORM operations are `async`. Always `await` them:

```python
# Create
post = await Post.objects.create(
    title="Hello World",
    slug="hello-world",
    content="My first post.",
    is_published=True,
)

# Fetch all
posts = await Post.objects.all()

# Filter
published = await Post.objects.filter(is_published=True).order_by("-created_at")

# Get one (raises DoesNotExist if not found)
post = await Post.objects.get(slug="hello-world")

# Get or None
post = await Post.objects.get_or_none(slug="hello-world")

# Update
await Post.objects.filter(id=1).update(is_published=True)

# Delete
await Post.objects.filter(id=1).delete()
```

## Signals

React to model events:

```python title="posts/models.py"
from buraq.signals import post_save

@post_save.connect
async def on_post_save(sender, instance, created, **kwargs):
    if created:
        print(f"New post created: {instance.title}")
```

Next: [Views & URLs →](views-urls.md)
