# Aggregates

Aggregates collapse many rows into a single computed value. Buraq provides `Count`, `Sum`, `Avg`, `Min`, `Max`, `StdDev`, and `Variance`.

```python
from buraq.orm.aggregates import Count, Sum, Avg, Min, Max, StdDev, Variance
```

## aggregate() — single row result

Run one or more aggregates and get a dict back:

```python
result = await Post.objects.aggregate(
    total=Count("id"),
    total_views=Sum("views"),
    avg_views=Avg("views"),
    min_views=Min("views"),
    max_views=Max("views"),
)
# → {"total": 42, "total_views": 8400, "avg_views": 200.0, ...}
```

Combine with filters:

```python
result = await Post.objects.filter(is_published=True).aggregate(
    published=Count("id"),
    avg_views=Avg("views"),
)
```

## annotate() — grouped results

Group rows with `values()` then annotate each group:

```python
# Posts per author
rows = await Post.objects.values("author_id").annotate(post_count=Count("id"))
# → [{"author_id": 1, "post_count": 5}, {"author_id": 2, "post_count": 3}, ...]

# Average views per category
rows = await Post.objects.values("category_id").annotate(avg_views=Avg("views"))
```

Multiple annotations at once:

```python
rows = await (
    Post.objects
    .values("author_id")
    .annotate(
        post_count=Count("id"),
        total_views=Sum("views"),
        max_views=Max("views"),
    )
)
```

## Count — distinct and all rows

```python
# Count all rows
Count("id")

# Count distinct values
Count("category_id", distinct=True)

# Count(*) — no field needed
Count()
```

## StdDev and Variance

```python
result = await Post.objects.aggregate(
    std=StdDev("views"),
    var=Variance("views"),
)
```

!!! note "Database support"
    `StdDev` and `Variance` require PostgreSQL or MySQL. SQLite does not support them natively.

## default= — COALESCE fallback

Pass `default=` to any aggregate to get a defined value instead of `NULL` when the result set is empty:

```python
result = await Post.objects.filter(is_published=False).aggregate(
    total=Count("id", default=0),      # → 0, not None
    avg_views=Avg("views", default=0.0),
)
```

The ORM wraps the aggregate in `COALESCE(agg, default)`. Without `default=`, aggregating an empty set returns `None` in Python.

## Bitwise aggregates

`BitAnd`, `BitOr`, and `BitXor` compute bitwise aggregates across all rows in the group. They are available on any database that exposes `bit_and()`, `bit_or()`, and `bit_xor()` aggregate functions (PostgreSQL, MariaDB 10.3+, MySQL 8+).

```python
from buraq.orm.aggregates import BitAnd, BitOr, BitXor

# Effective permissions bitmap across all active users
result = await User.objects.filter(is_active=True).aggregate(
    all_perms=BitAnd("permission_bits"),   # bits set in ALL users
    any_perm=BitOr("permission_bits"),     # bits set in ANY user
    exclusive=BitXor("permission_bits"),   # bits set in an odd number of users
)
```

Use in `annotate()` to compute bitwise aggregates per group:

```python
rows = await User.objects.values("team_id").annotate(
    team_perms=BitOr("permission_bits")
)
```

## Reference

| Class | SQL function | Notes |
|---|---|---|
| `Count(field="*", distinct=False, default=None)` | `COUNT(field)` | Counts rows; `distinct=True` deduplicates |
| `Sum(field, default=None)` | `SUM(field)` | |
| `Avg(field, default=None)` | `AVG(field)` | |
| `Min(field, default=None)` | `MIN(field)` | |
| `Max(field, default=None)` | `MAX(field)` | |
| `StdDev(field, default=None)` | `STDDEV(field)` | PostgreSQL / MySQL only |
| `Variance(field, default=None)` | `VARIANCE(field)` | PostgreSQL / MySQL only |
| `BitAnd(field)` | `bit_and(field)` | PostgreSQL, MariaDB 10.3+, MySQL 8+ |
| `BitOr(field)` | `bit_or(field)` | PostgreSQL, MariaDB 10.3+, MySQL 8+ |
| `BitXor(field)` | `bit_xor(field)` | PostgreSQL, MariaDB 10.3+, MySQL 8+ |
| `AnyValue(field)` | `any_value(field)` | MySQL 8.0.2+, MariaDB 10.3+ |

## AnyValue

Returns an arbitrary non-NULL value from the group. Useful in `GROUP BY` queries where a column is functionally dependent on the group key but not listed in `GROUP BY` — avoids wrapping in `MAX()` or `MIN()` when any value will do.

```python
from buraq.orm.aggregates import AnyValue

# Each customer's arbitrary sample order note — we don't care which one
rows = await Order.objects.values("customer_id").annotate(
    sample_note=AnyValue("note")
)
```

!!! note "Database support"
    `AnyValue` maps to the native `any_value()` SQL aggregate, available on
    **MySQL 8.0.2+** and **MariaDB 10.3+**. On PostgreSQL (which has no
    `any_value()` until PG 16) use `Max` or `Min` as a portable substitute.
