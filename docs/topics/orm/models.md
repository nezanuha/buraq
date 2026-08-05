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
| `SmallIntegerField()` | `int` | `SMALLINT` |
| `PositiveSmallIntegerField()` | `int` | `SMALLINT CHECK ≥ 0` |
| `PositiveBigIntegerField()` | `int` | `BIGINT CHECK ≥ 0` |
| `DurationField()` | `timedelta` | `INTERVAL` |
| `GenericIPAddressField()` | `str` | `VARCHAR(39)` |
| `BinaryField()` | `bytes` | `BLOB/BYTEA` |
| `NullBooleanField()` | `bool\|None` | `BOOLEAN` (nullable) |
| `AutoField()` | `int` | `INTEGER` (auto PK) |

## Choices

```python
from buraq import models

class Status(models.TextChoices):
    DRAFT     = "draft"
    PUBLISHED = "published"
    ARCHIVED  = "archived"

class Priority(models.IntegerChoices):
    LOW    = 1
    MEDIUM = 2
    HIGH   = 3

class Article(models.Model):
    status   = models.CharField(max_length=20, choices=Status.choices())
    priority = models.IntegerField(choices=Priority.choices(), default=Priority.LOW)
```

Usage:
```python
article.status == Status.PUBLISHED        # True
Status.values()                           # ["draft", "published", "archived"]
Status.choices()                          # [("draft", "Draft"), ("published", "Published"), ...]
```

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
from buraq import models

class Comment(models.Model):
    post   = models.ForeignKey("Post", on_delete=models.CASCADE)
    author = models.ForeignKey("User", on_delete=models.SET_NULL, null=True)
```

| Constant | SQL | Behaviour |
|---|---|---|
| `models.CASCADE` | `ON DELETE CASCADE` | Delete related rows |
| `models.PROTECT` | `ON DELETE RESTRICT` | Block delete if related rows exist |
| `models.SET_NULL` | `ON DELETE SET NULL` | Set FK to NULL (requires `null=True`) |
| `models.SET_DEFAULT` | `ON DELETE SET DEFAULT` | Set FK to field default |
| `models.DO_NOTHING` | `ON DELETE NO ACTION` | Leave related rows unchanged |
| `models.RESTRICT` | `ON DELETE RESTRICT` | Like PROTECT; raises IntegrityError |

## help_text

```python
class Post(models.Model):
    slug = models.SlugField(
        unique=True,
        help_text="URL-friendly identifier, e.g. 'my-first-post'.",
    )
```

`help_text` is stored on the field and surfaced by `ModelForm` automatically.

## TextField with max_length

```python
# No limit (stores as TEXT column)
body = models.TextField()

# With limit (stores as VARCHAR)
excerpt = models.TextField(max_length=500)
```

## DurationField

Stores a Python `timedelta`. Maps to `INTERVAL` on PostgreSQL, integer microseconds on SQLite.

```python
class Task(models.Model):
    name     = models.CharField(max_length=200)
    duration = models.DurationField(null=True)

# Store
task = await Task.objects.create(name="Build", duration=timedelta(hours=2, minutes=30))

# Query
from datetime import timedelta
long_tasks = await Task.objects.filter(duration__gte=timedelta(hours=1))
```

## GenericIPAddressField

Stores IPv4 or IPv6 addresses as a string (max 39 chars for full IPv6).

```python
class Server(models.Model):
    name    = models.CharField(max_length=100)
    ip_addr = models.GenericIPAddressField(protocol="both")  # "ipv4", "ipv6", or "both"
```

## PositiveBigIntegerField

Like `BigIntegerField` but enforces a `>= 0` constraint at the database level.

```python
class Product(models.Model):
    name  = models.CharField(max_length=200)
    stock = models.PositiveBigIntegerField(default=0)
```

## ManyToManyField symmetrical

```python
# Default: symmetrical=True (A follows B implies B follows A)
followers = models.ManyToManyField("self")

# symmetrical=False — for directed graphs (A follows B ≠ B follows A)
following = models.ManyToManyField("self", symmetrical=False)
```

## Meta class

```python
class Post(models.Model):
    title = models.CharField(max_length=200)

    class Meta:
        table_name = "blog_posts"   # custom table name (default: class name lowercased + "s")
```
