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
Post.objects.filter(title__iexact="hello world")          # case-insensitive exact
Post.objects.filter(views__range=(100, 500))              # BETWEEN 100 AND 500
Post.objects.filter(created_at__year=2024)                # extract year
Post.objects.filter(created_at__month=6)                  # extract month
Post.objects.filter(created_at__day=15)                   # extract day
```

### Full lookup reference

| Lookup | SQL equivalent | Notes |
|---|---|---|
| `exact` | `= value` | Default when no lookup given |
| `iexact` | `ILIKE value` | Case-insensitive exact |
| `contains` | `LIKE %value%` | |
| `icontains` | `ILIKE %value%` | Case-insensitive |
| `startswith` | `LIKE value%` | |
| `istartswith` | `ILIKE value%` | Case-insensitive |
| `endswith` | `LIKE %value` | |
| `iendswith` | `ILIKE %value` | Case-insensitive |
| `gt` | `> value` | |
| `gte` | `>= value` | |
| `lt` | `< value` | |
| `lte` | `<= value` | |
| `in` | `IN (...)` | Pass a list |
| `isnull` | `IS NULL` / `IS NOT NULL` | Pass `True` or `False` |
| `range` | `BETWEEN v1 AND v2` | Pass a 2-tuple |
| `year` | `EXTRACT(year ...)` | DateTimeField only |
| `month` | `EXTRACT(month ...)` | DateTimeField only |
| `day` | `EXTRACT(day ...)` | DateTimeField only |

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

## get_or_create()

Fetch an object matching kwargs, or create it if it doesn't exist. Returns `(instance, created)`:

```python
post, created = await Post.objects.get_or_create(
    slug="hello-world",
    defaults={"title": "Hello World", "content": "..."},
)
# created=True  → new object was inserted
# created=False → existing object was returned
```

`defaults` are only used when creating — they are not used in the lookup.

## update_or_create()

Like `get_or_create()` but updates the existing object with `defaults` if found:

```python
post, created = await Post.objects.update_or_create(
    slug="hello-world",
    defaults={"title": "Updated Title", "views": 0},
)
```

## none() — empty queryset

Return a queryset that always yields zero results — useful for conditional query building:

```python
qs = Post.objects.none()
results = await qs.all()   # → []
count = await qs.count()   # → 0
```

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

## distinct()

Remove duplicate rows from results:

```python
# Unique category IDs
category_ids = await Post.objects.values_list("category_id", flat=True).distinct().all()
```

## select_related() / prefetch_related()

Eagerly load related objects to avoid N+1 queries:

```python
# JOIN load (one query) — use for ForeignKey / OneToOneField
posts = await Post.objects.select_related("author").all()

# Subquery load (two queries) — use for ManyToManyField / reverse FK
posts = await Post.objects.prefetch_related("tags").all()

# Chain both
posts = await Post.objects.select_related("author").prefetch_related("tags").all()
```

For custom filtering on prefetched relations, use a `Prefetch` object (see [Prefetch objects](#prefetch-objects) below).

## refresh_from_db()

Reload an instance's fields from the database — useful after an out-of-band
update (e.g. a `bulk_update` that bypassed the object):

```python
post = await Post.objects.get(id=1)
# … some other code updates the row in the DB …
await post.refresh_from_db()           # reload all fields

# Reload only specific fields (avoids fetching heavy columns)
await post.refresh_from_db(fields=["status", "views"])
```

## last()

Return the last object by primary key, or `None`:

```python
latest_post = await Post.objects.last()
latest_published = await Post.objects.filter(is_published=True).last()
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

# Bulk update — update specific fields on a list of instances
posts = await Post.objects.filter(is_published=False).all()
for post in posts:
    post.status = "archived"
await Post.objects.bulk_update(posts, fields=["status"])
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

## explain()

Retrieve the database's query plan for debugging slow queries:

```python
# Basic EXPLAIN
plan = await Post.objects.filter(is_published=True).explain()
print(plan)

# With ANALYZE (actually executes the query — PostgreSQL / SQLite)
plan = await Post.objects.filter(is_published=True).explain(analyze=True)

# With VERBOSE (PostgreSQL)
plan = await Post.objects.filter(is_published=True).explain(analyze=True, verbose=True)
```

The returned value is a string containing the database's plan output.

## alias()

Create a named subquery alias so the same queryset can be reused in multiple
`filter()` or `annotate_expr()` calls without repeating SQL:

```python
# Build once
recent_posts = Post.objects.filter(created_at__gte=cutoff).alias("recent")

# Reuse in outer queries
popular = await Post.objects.filter(id__in=recent_posts, views__gte=100).all()
long_read = await Post.objects.filter(id__in=recent_posts, read_time__gte=10).all()
```

## Prefetch objects

`Prefetch` gives you fine-grained control over the queryset used when calling
`prefetch_related()`.  Import it from `buraq.models` (or `buraq.orm.prefetch`):

```python
from buraq.models import Prefetch

# Load only approved comments, ordered by date
posts = await Post.objects.prefetch_related(
    Prefetch(
        "comments",
        queryset=Comment.objects.filter(approved=True).order_by("-created_at"),
    )
).all()

# Access the pre-fetched set on each instance
for post in posts:
    approved = post._prefetched_comments   # list[Comment]
```

Store the result under a custom attribute with `to_attr`:

```python
posts = await Post.objects.prefetch_related(
    Prefetch("comments", queryset=Comment.objects.filter(approved=True), to_attr="approved_comments"),
    Prefetch("comments", queryset=Comment.objects.filter(approved=False), to_attr="pending_comments"),
).all()
```

## get_or_create() — race safety

`get_or_create` uses a **try-create-catch-IntegrityError** pattern internally,
so it is safe under concurrent requests: if two coroutines race to create the
same row, the loser catches the database's `IntegrityError` and falls back to
fetching the row the winner created — no `DoesNotExist` is leaked.

```python
post, created = await Post.objects.get_or_create(
    slug="hello-world",
    defaults={"title": "Hello World", "content": "..."},
)
```

`update_or_create` is race-safe by the same mechanism.

## bulk_update — single round-trip

`bulk_update` sends a single parameterised UPDATE statement (via `sa.bindparam`
bulk binding) regardless of how many instances are passed — no N-query loop:

```python
posts = await Post.objects.filter(is_published=False).all()
for post in posts:
    post.status = "archived"

# One SQL statement, no matter how many posts
await Post.objects.bulk_update(posts, fields=["status"])
```
