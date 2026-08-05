# Advanced Querying

## select_for_update

Lock rows for the duration of a transaction — prevents concurrent writes.

```python
# Lock post rows while processing a payment
posts = await Post.objects.filter(status="pending").select_for_update()

# Non-blocking — skip already-locked rows
posts = await Post.objects.filter(status="pending").select_for_update(skip_locked=True)

# Raise immediately if rows are locked
posts = await Post.objects.filter(status="pending").select_for_update(nowait=True)
```

Use inside a database transaction to ensure the lock is held until the transaction commits.

---

## earliest / latest

Return the earliest or latest object by a field.

```python
# Earliest created post
first_post = await Post.objects.earliest("created_at")

# Latest by primary key (default)
last_post = await Post.objects.latest()

# Latest by multiple fields
last_post = await Post.objects.latest("created_at", "id")
```

---

## dates / datetimes

Return a sorted list of distinct date values for a field.

```python
# All distinct years that have posts
years = await Post.objects.dates("created_at", "year")
# → [datetime.date(2023, 1, 1), datetime.date(2024, 1, 1)]

# All distinct months
months = await Post.objects.dates("created_at", "month")

# All distinct days
days = await Post.objects.dates("published_on", "day")
```

`datetimes()` is the same but returns `datetime` objects and supports finer granularity:

```python
hours = await Event.objects.datetimes("start_time", "hour")
```

---

## raw SQL

Run raw SQL when ORM expressions aren't enough.

```python
rows = await Post.objects.raw(
    "SELECT id, title, views FROM posts WHERE views > :min_views",
    {"min_views": 100},
)
# → [{"id": 1, "title": "...", "views": 250}, ...]
```

Parameters use `:name` style (SQLAlchemy `text()` parameters).

---

## Annotating with expressions

Use `annotate()` to attach any expression — aggregate, function, window, or Case — to each result row.

```python
from buraq.orm import functions as Fn
from buraq.orm.expressions import Case, When, Value
from buraq.orm.window import Window, Rank

posts = await Post.objects.values("author_id").annotate(
    post_count=Count("id"),
    latest_title=Fn.Upper("title"),
    rank=Window(Rank(), order_by="-views"),
    label=Case(
        When(is_featured=True, then=Value("featured")),
        default=Value("regular"),
    ),
)
```
