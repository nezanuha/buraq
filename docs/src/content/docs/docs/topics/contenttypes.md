---
title: "Content Types"
description: "buraq.contrib.contenttypes provides a generic foreign key mechanism — a way to link any model to any other model without a hard-coded foreign key."
---

`buraq.contrib.contenttypes` provides a generic foreign key mechanism — a way to link any model to any other model without a hard-coded foreign key.

## Setup

Add to `INSTALLED_APPS` and run migrations:

```python
INSTALLED_APPS = [
    "buraq.contrib.contenttypes",
    ...
]
```

## ContentType model

`ContentType` stores a row for every installed model:

```python
from buraq.contrib.contenttypes.models import ContentType

ct = await ContentType.get_for_model(Post)
# <ContentType blog.post>

ct.app_label  # "blog"
ct.model      # "post"
```

## GenericForeignKey

Link any model to any other model:

```python
from sqlalchemy import Column, Integer
from buraq.orm.base import Model
from buraq.contrib.contenttypes.fields import GenericForeignKey

class Comment(Model):
    content_type_id = Column(Integer, nullable=True)
    object_id = Column(Integer, nullable=True)
    content_object = GenericForeignKey("content_type_id", "object_id")
    body = Column(String(500))
```

Resolve the linked object asynchronously:

```python
comment = await Comment.objects.get(id=1)
post = await comment.content_object   # Post instance or None
```

## Creating a generic relation

```python
from buraq.contrib.contenttypes.models import ContentType

ct = await ContentType.get_for_model(Post)
post = await Post.objects.get(id=42)

comment = await Comment.objects.create(
    content_type_id=ct.id,
    object_id=post.id,
    body="Great post!",
)
```

## ContentType lookup helpers

```python
ct = await ContentType.get_for_model(Post)

# Look up by natural key (app_label, model)
ct = await ContentType.get_by_natural_key("blog", "post")

# Get the Python class for a ContentType row
model_class = ct.model_class()   # returns Post class, or None if not importable
```

## `GenericRelation` — reverse accessor

Add `GenericRelation` to the *target* model to query all objects that point to it via a `GenericForeignKey`:

```python
from buraq.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from buraq.orm.base import Model
from sqlalchemy import Column, Integer, String

class Comment(Model):
    content_type_id = Column(Integer)
    object_id       = Column(Integer)
    content_object  = GenericForeignKey()
    body            = Column(String(500))

class Post(Model):
    title    = Column(String(200))
    comments = GenericRelation(Comment)   # reverse accessor
```

Query through the reverse relation:

```python
post = await Post.objects.get(id=1)

# All comments for this post
comments = await post.comments.all()

# Filtered
recent = await post.comments.filter(created_at__gte=since)

# Count
n = await post.comments.count()

# Create via relation (content_type_id and object_id filled automatically)
new_comment = await post.comments.create(body="Nice!")
```

Use a dotted string to avoid circular imports:

```python
class Post(Model):
    comments = GenericRelation("blog.models.Comment")
```
