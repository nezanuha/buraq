# Querying

All query methods are `async`. Always `await` them.

## Basic operations

```python
# All records
posts = await Post.objects.all()

# Filter
posts = await Post.objects.filter(is_published=True)

# Exclude
posts = await Post.objects.exclude(is_published=False)

# Get single record (raises DoesNotExist if not found)
post = await Post.objects.get(id=1)
post = await Post.objects.get(slug="hello-world")

# Get or None
post = await Post.objects.get_or_none(slug="hello-world")

# Count
n = await Post.objects.count()
n = await Post.objects.filter(is_published=True).count()

# Check existence
exists = await Post.objects.filter(slug="hello").exists()

# Create
post = await Post.objects.create(title="Hello", slug="hello", content="...")

# Update
await Post.objects.filter(id=1).update(is_published=True)

# Delete
await Post.objects.filter(is_published=False).delete()

# Save an instance
post = await Post.objects.get(id=1)
post.title = "Updated title"
await post.save()

# Delete an instance
await post.delete()
```

## Ordering

```python
# Ascending
posts = await Post.objects.all().order_by("created_at")

# Descending
posts = await Post.objects.all().order_by("-created_at")

# Multiple fields
posts = await Post.objects.all().order_by("-is_published", "title")
```

## Limiting

```python
posts = await Post.objects.all().limit(10)
posts = await Post.objects.all().limit(10).offset(20)
```

## Lookup expressions

```python
Post.objects.filter(title__contains="Django")
Post.objects.filter(title__icontains="django")   # case-insensitive
Post.objects.filter(title__startswith="Hello")
Post.objects.filter(title__istartswith="hello")
Post.objects.filter(title__endswith="World")
Post.objects.filter(created_at__gt=some_date)    # greater than
Post.objects.filter(created_at__gte=some_date)   # greater than or equal
Post.objects.filter(views__lt=100)               # less than
Post.objects.filter(views__lte=100)              # less than or equal
Post.objects.filter(title__in=["A", "B", "C"])
Post.objects.filter(category_id__isnull=True)
```

## Q objects — complex filters

```python
from buraq.orm.query import Q

# OR
posts = await Post.objects.filter(
    Q(title__contains="Django") | Q(title__contains="FastAPI")
)

# AND
posts = await Post.objects.filter(
    Q(is_published=True) & Q(views__gt=100)
)

# NOT
posts = await Post.objects.filter(~Q(is_published=False))

# Nested
posts = await Post.objects.filter(
    Q(is_published=True) & (Q(title__contains="async") | Q(views__gt=500))
)

# XOR — exactly one condition must be true
posts = await Post.objects.filter(
    Q(is_featured=True) ^ Q(is_editor_pick=True)
)
```

XOR is emulated as `(A OR B) AND NOT (A AND B)` for full compatibility across SQLite, PostgreSQL, and MySQL.

## values() and values_list()

Return dicts or tuples instead of model instances — useful for serialization and aggregation:

```python
# List of dicts
posts = await Post.objects.values("id", "title", "views").all()
# → [{"id": 1, "title": "Hello", "views": 42}, ...]

# List of tuples
posts = await Post.objects.values_list("id", "title").all()
# → [(1, "Hello"), (2, "World"), ...]

# Single-column flat list
ids = await Post.objects.values_list("id", flat=True).all()
# → [1, 2, 3, ...]

# Combine with filters and ordering
slugs = await (
    Post.objects
    .filter(is_published=True)
    .order_by("-created_at")
    .values_list("slug", flat=True)
    .all()
)
```

## annotate_expr()

Add arbitrary SQL expression columns to each result row. Accepts aggregates, window functions, ORM expressions, or raw SQLAlchemy constructs:

```python
from buraq.orm.aggregates import Count
from buraq.orm.window import Window, Rank
from buraq.orm.expressions import Case, When, Value

posts = await Post.objects.annotate_expr(
    rank=Window(Rank(), partition_by="category_id", order_by="-views"),
    label=Case(
        When(is_featured=True, then=Value("featured")),
        default=Value("regular"),
    ),
).all()
```

Combined with `values()`:

```python
rows = await Post.objects.values("author_id").annotate_expr(
    post_count=Count("id")
).all()
# → [{"author_id": 1, "post_count": 5}, ...]
```

## F expressions — field references

```python
from buraq.orm.query import F

# Increment a counter without a read-modify-write
await Post.objects.filter(id=1).update(views=F("views") + 1)

# Compare two fields
posts = await Post.objects.filter(updated_at__gt=F("created_at"))
```

## Pagination

```python
from buraq.paginator import Paginator

paginator = Paginator(Post.objects.filter(is_published=True), per_page=10)
page      = await paginator.page(request.query_params.get("page", 1))

# page.object_list — items on this page
# page.has_next() / page.has_previous()
# page.next_page_number() / page.previous_page_number()
# paginator.num_pages
```

## Bulk operations

```python
# Bulk create
await Post.objects.bulk_create([
    {"title": "Post 1", "slug": "post-1", "content": "..."},
    {"title": "Post 2", "slug": "post-2", "content": "..."},
])

# With ignore_conflicts (skip duplicates)
await Post.objects.bulk_create(records, ignore_conflicts=True)
```

## Streaming large querysets

```python
async for post in Post.objects.filter(is_published=True).iterator():
    process(post)   # memory-efficient — doesn't load all at once
```

## Deferred loading

Load only specific columns; remaining columns are fetched lazily when accessed.

```python
# Load only title and slug — content and other fields are deferred
posts = await Post.objects.only("title", "slug").all()

# Load everything except the large content column
posts = await Post.objects.defer("content").all()
```

## Locking rows — select_for_update

```python
# Lock rows for the duration of the current transaction
posts = await Post.objects.filter(is_published=False).select_for_update().all()

# Non-blocking — skip rows that are already locked
posts = await Post.objects.filter(status="pending").select_for_update(skip_locked=True).all()

# Raise immediately if any row is locked
posts = await Post.objects.filter(status="pending").select_for_update(nowait=True).all()
```

## Earliest and latest

```python
# First record by created_at
oldest = await Post.objects.earliest("created_at")

# Most recent record by created_at
newest = await Post.objects.latest("created_at")

# Defaults to primary key if no field is specified
first  = await Post.objects.earliest()
last   = await Post.objects.latest()
```

## Date and datetime truncation

```python
# Distinct years that have at least one post
years = await Post.objects.dates("created_at", "year")
# → [datetime.date(2023, 1, 1), datetime.date(2024, 1, 1), ...]

# Distinct months
months = await Post.objects.dates("created_at", "month")

# Datetime precision (requires DateTimeField)
hours = await Post.objects.datetimes("created_at", "hour")
# kind: "year" | "month" | "day" | "hour" | "minute" | "second"
```

## Raw SQL

Use when ORM expressions can't express what you need.

```python
rows = await Post.objects.raw(
    "SELECT id, title FROM posts WHERE views > :min_views",
    {"min_views": 100},
)
# → [{"id": 1, "title": "..."}, ...]
```

## Annotating with arbitrary expressions

```python
from buraq.orm.window import RowNumber, Window

posts = await Post.objects.annotate_expr(
    row_num=RowNumber(Window(order_by="id")),
).all()
```

## in_bulk

```python
# Fetch a dict keyed by primary key
post_map = await Post.objects.in_bulk([1, 2, 3])
# → {1: <Post id=1>, 2: <Post id=2>, 3: <Post id=3>}

# Keyed by a different field
slug_map = await Post.objects.in_bulk(["hello", "world"], field_name="slug")
```
