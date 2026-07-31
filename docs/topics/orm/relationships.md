# Relationships

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
    on_delete  = "CASCADE",    # CASCADE | SET NULL | RESTRICT | SET DEFAULT | NO ACTION
    nullable   = False,
    db_index   = True,         # adds an index on the FK column (default: True)
)
```

## Querying across relationships

```python
# Filter comments by post fields (join via filter)
comments = await Comment.objects.filter(post_id__in=[1, 2, 3])

# Get all posts in a category
posts = await Post.objects.filter(category_id=category.id)
```

!!! note "No lazy loading"
    Buraq does not support lazy loading of related objects (it can't — we're async). Always fetch related objects explicitly with a separate query or use `select_related` (planned).
