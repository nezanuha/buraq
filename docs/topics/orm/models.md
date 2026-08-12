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

All `Meta` options are optional.

```python
from buraq import models

class Post(models.Model):
    title     = models.CharField(max_length=200)
    author_id = models.ForeignKey("buraq_users")
    views     = models.IntegerField(default=0)

    class Meta:
        table_name          = "blog_posts"          # override table name (default: lowercased plural)
        ordering            = ["-created_at"]       # default ORDER BY — prefix with - for DESC
        verbose_name        = "blog post"           # human-readable singular name
        verbose_name_plural = "blog posts"          # human-readable plural (auto-derived if omitted)
        unique_together     = [["author_id", "title"]]  # composite unique constraint(s)
        indexes = [
            models.Index(fields=["title"]),
            models.Index(fields=["author_id", "created_at"], name="post_author_date_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["author_id", "title"], name="unique_author_title"),
            models.CheckConstraint(check="views >= 0", name="positive_views"),
        ]
```

### Meta options reference

| Option | Type | Description |
|---|---|---|
| `table_name` | `str` | Database table name. Also accepted as `db_table` (Django alias). |
| `ordering` | `list[str]` | Default sort order. Prefix field name with `-` for descending. |
| `verbose_name` | `str` | Singular display name used in admin and error messages. |
| `verbose_name_plural` | `str` | Plural display name. Defaults to `verbose_name + "s"`. |
| `unique_together` | `list[list[str]]` | Shorthand for composite unique constraints. |
| `indexes` | `list[Index]` | Database indexes to create on the table. |
| `constraints` | `list[UniqueConstraint \| CheckConstraint]` | Named database-level constraints. |

### Index

```python
models.Index(fields=["field1", "field2"], name="optional_name", unique=False)
```

`unique=True` creates a unique index (equivalent to `UniqueConstraint` but without a name requirement).

### UniqueConstraint

```python
models.UniqueConstraint(fields=["author_id", "slug"], name="unique_author_slug")
```

### CheckConstraint

Enforce a SQL-level condition. The `check` string is passed directly to the database:

```python
models.CheckConstraint(check="price > 0", name="positive_price")
models.CheckConstraint(check="end_date >= start_date", name="valid_date_range")
```

## Model._state

Every model instance carries a `_state` object that reflects its persistence status.

```python
post = Post(title="Draft")
post._state.adding   # → True  (not yet saved)

await post.save()
post._state.adding   # → False (row exists in the database)
```

| Attribute | Type | Meaning |
|---|---|---|
| `adding` | `bool` | `True` if the instance has never been `save()`d; `False` after the first successful insert |

## pk alias

The `pk` attribute is a read-only alias for whatever field is the model's primary key (usually `id`). Use it in generic code that shouldn't assume the PK column name:

```python
post = await Post.objects.get(id=1)
post.pk        # → 1  (same as post.id)
Post.objects.filter(pk=1)  # equivalent to filter(id=1)
```

## get_absolute_url()

Override to return the canonical URL for a model instance. Used by the admin and generic views:

```python
class Post(models.Model):
    slug = models.SlugField(unique=True)

    def get_absolute_url(self) -> str:
        from buraq.urls import reverse
        return reverse("post-detail", kwargs={"slug": self.slug})
```

Calling the base implementation raises `NotImplementedError`.

## natural_key()

Override to return a tuple that uniquely identifies the instance without the surrogate PK. Used by serializers when `use_natural_primary_keys=True`:

```python
class User(models.Model):
    username = models.CharField(max_length=150, unique=True)

    def natural_key(self) -> tuple:
        return (self.username,)
```

Calling the base implementation raises `NotImplementedError`.

## RelatedManager — reverse FK accessor

Every ForeignKey field automatically creates a reverse accessor on the parent model. By default the accessor name is `{child_model_name_lower}_set`:

```python
class Comment(models.Model):
    post = models.ForeignKey("Post", on_delete=models.CASCADE)

# Access comments for a post
post = await Post.objects.get(id=1)
comments = await post.comment_set.all()
recent = await post.comment_set.filter(is_approved=True).order_by("-created_at").all()

# Create through the relation
new_comment = await post.comment_set.create(body="Great post!")

# Add / remove existing instances
await post.comment_set.add(comment)
await post.comment_set.remove(comment)
await post.comment_set.clear()         # remove all
await post.comment_set.set([c1, c2])   # replace all
```

Customise the accessor name with `related_name=`:

```python
class Comment(models.Model):
    post = models.ForeignKey("Post", on_delete=models.CASCADE, related_name="comments")

comments = await post.comments.all()
```

## AutoField variants

| Field | SQL type | When to use |
|---|---|---|
| `AutoField()` | `INTEGER AUTOINCREMENT` | Default PK for most tables |
| `SmallAutoField()` | `SMALLINT` / `SMALLSERIAL` | Tables guaranteed to have < 32 768 rows |
| `BigAutoField()` | `BIGINT` / `BIGSERIAL` | Tables that may exceed 2 billion rows |

Set the default PK type project-wide in settings:

```python
DEFAULT_AUTO_FIELD = "buraq.orm.fields.BigAutoField"
```

## Model validation

Buraq models support the same pre-save validation chain as Django.

### full_clean()

Run all validation steps in order. Called automatically by `ModelForm`; call
manually when saving outside a form:

```python
from buraq.exceptions import ValidationError

try:
    await post.full_clean()
    await post.save()
except ValidationError as e:
    print(e.message_dict)
```

The chain is: `clean_fields()` → `clean()` → `validate_unique()`.

### clean_fields()

Validates each field value using the field's built-in validators.
Raises `ValidationError` with per-field messages if any field fails:

```python
await post.clean_fields()           # validate all fields
await post.clean_fields(exclude=["content"])  # skip specific fields
```

### clean()

Override to add cross-field or object-level validation logic:

```python
class Event(models.Model):
    start = models.DateTimeField()
    end   = models.DateTimeField()

    async def clean(self):
        if self.end <= self.start:
            raise ValidationError({"end": "End must be after start."})
```

### validate_unique()

Checks that all `unique=True` fields and `unique_together` constraints are not
violated by an existing database row. Raises `ValidationError` if a duplicate
is found:

```python
await event.validate_unique()
await event.validate_unique(exclude=["slug"])  # skip specific fields
```

---

## GeneratedField

A read-only field whose value is computed by the database engine on every INSERT or UPDATE.

```python
from buraq import models

class Product(models.Model):
    price      = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate   = models.FloatField(default=0.2)
    price_incl = models.GeneratedField(
        expression="price * (1 + tax_rate)",
        output_field=models.DecimalField(max_digits=10, decimal_places=2),
        db_persist=True,
    )
```

| Parameter | Description |
|---|---|
| `expression` | SQL expression string evaluated by the database |
| `output_field` | A field instance describing the column type |
| `db_persist` | `True` (default) = STORED column (computed on write); `False` = VIRTUAL (computed on read, not supported by all databases) |

Generated columns are database-managed and cannot be assigned in Python. Database support: PostgreSQL 12+, MySQL 5.7+, SQLite 3.31+.

---

## CompositePrimaryKey

Declares a multi-column primary key. Set `primary_key` on the model's `Meta` class instead of relying on the implicit auto-increment `id` column.

```python
from buraq import models

class OrderItem(models.Model):
    order_id   = models.ForeignKey("orders", on_delete=models.CASCADE)
    product_id = models.ForeignKey("products", on_delete=models.CASCADE)
    quantity   = models.IntegerField(default=1)

    class Meta:
        primary_key = models.CompositePrimaryKey("order_id", "product_id")
```

Models with a composite primary key have no `id` attribute. Use the individual key columns to look up rows:

```python
item = await OrderItem.objects.get(order_id=1, product_id=5)
```
