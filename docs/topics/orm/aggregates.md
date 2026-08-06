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

## Reference

| Class | SQL function | Notes |
|---|---|---|
| `Count(field="*", distinct=False)` | `COUNT(field)` | Counts rows; `distinct=True` deduplicates |
| `Sum(field)` | `SUM(field)` | |
| `Avg(field)` | `AVG(field)` | |
| `Min(field)` | `MIN(field)` | |
| `Max(field)` | `MAX(field)` | |
| `StdDev(field)` | `STDDEV(field)` | PostgreSQL / MySQL only |
| `Variance(field)` | `VARIANCE(field)` | PostgreSQL / MySQL only |
