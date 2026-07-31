# Models

## Defining a model

```python
from buraq import models


class Post(models.Model):
    title        = models.CharField(max_length=200)
    slug         = models.SlugField(unique=True)
    content      = models.TextField()
    is_published = models.BooleanField(default=False)
    views        = models.IntegerField(default=0)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        table_name = "posts"
```

## Field types

| Field | Python type | SQL type |
|---|---|---|
| `CharField(max_length=N)` | `str` | `VARCHAR(N)` |
| `TextField()` | `str` | `TEXT` |
| `IntegerField()` | `int` | `INTEGER` |
| `PositiveIntegerField()` | `int` | `INTEGER CHECK > 0` |
| `BigIntegerField()` | `int` | `BIGINT` |
| `FloatField()` | `float` | `FLOAT` |
| `DecimalField(max_digits, decimal_places)` | `Decimal` | `NUMERIC` |
| `BooleanField()` | `bool` | `BOOLEAN` |
| `DateField()` | `date` | `DATE` |
| `DateTimeField()` | `datetime` | `DATETIME` |
| `TimeField()` | `time` | `TIME` |
| `EmailField()` | `str` | `VARCHAR(254)` |
| `URLField()` | `str` | `VARCHAR(200)` |
| `SlugField()` | `str` | `VARCHAR(50)` |
| `UUIDField()` | `UUID` | `VARCHAR(36)` |
| `JSONField()` | `dict/list` | `JSON` |
| `ForeignKey(model)` | model instance | `INTEGER` (FK) |

## Field options

All fields accept these common options:

```python
models.CharField(
    max_length  = 200,
    required    = True,    # NOT NULL in SQL
    nullable    = False,   # same as required=False
    default     = "",      # default value
    unique      = False,   # UNIQUE constraint
    db_index    = False,   # CREATE INDEX
    primary_key = False,   # PRIMARY KEY
)
```

## DateTimeField auto options

```python
# Set to current time when the record is CREATED (never updated)
created_at = models.DateTimeField(auto_now_add=True)

# Set to current time every time the record is SAVED
updated_at = models.DateTimeField(auto_now=True)
```

!!! note
    `auto_now=True` and `auto_now_add=True` cannot both be set on the same field.

## ForeignKey

```python
class Comment(models.Model):
    post   = models.ForeignKey("Post", on_delete="CASCADE")
    author = models.ForeignKey("User", on_delete="SET NULL", nullable=True)
```

`on_delete` options: `"CASCADE"`, `"SET NULL"`, `"RESTRICT"`, `"SET DEFAULT"`, `"NO ACTION"`

## Meta class

```python
class Post(models.Model):
    title = models.CharField(max_length=200)

    class Meta:
        table_name = "blog_posts"   # custom table name (default: class name lowercased + "s")
```
