# Content Types

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
