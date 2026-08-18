---
title: "Window Functions"
description: "Window functions compute values across a sliding partition of rows — without collapsing them into a single row the way aggregates do."
---

Window functions compute values across a sliding partition of rows — without collapsing them into a single row the way aggregates do.

```python
from buraq.orm.window import Window, RowNumber, Rank, Lag
```

## Basic usage

Attach a window function to a queryset with `annotate_expr()`:

```python
posts = await Post.objects.annotate_expr(
    row_num=Window(RowNumber(), order_by="-created_at")
).all()

for post in posts:
    print(post.row_num, post.title)
```

## PARTITION BY

Restart numbering for each group:

```python
posts = await Post.objects.annotate_expr(
    row_num=Window(RowNumber(), partition_by="author_id", order_by="-created_at")
).all()
```

Multiple partition columns:

```python
Window(Rank(), partition_by=["category_id", "author_id"], order_by="-views")
```

## ORDER BY inside the window

```python
# Ascending
Window(Rank(), order_by="views")

# Descending (prefix with -)
Window(Rank(), order_by="-views")

# Multiple fields
Window(DenseRank(), order_by=["category_id", "-views"])
```

## Ranking functions

| Function | SQL equivalent | Description |
|---|---|---|
| `RowNumber()` | `ROW_NUMBER()` | Unique sequential number per row |
| `Rank()` | `RANK()` | Rank with gaps after ties |
| `DenseRank()` | `DENSE_RANK()` | Rank without gaps |
| `PercentRank()` | `PERCENT_RANK()` | Relative rank as 0.0–1.0 |
| `CumeDist()` | `CUME_DIST()` | Cumulative distribution |
| `Ntile(n)` | `NTILE(n)` | Divide rows into n buckets |

```python
# Percentile ranking
posts = await Post.objects.annotate_expr(
    pct=Window(PercentRank(), order_by="views")
).all()

# Quartiles
posts = await Post.objects.annotate_expr(
    quartile=Window(Ntile(4), order_by="views")
).all()
```

## Value functions

Retrieve field values from other rows in the window:

| Function | Description |
|---|---|
| `Lag(field, offset=1, default=None)` | Value from N rows before |
| `Lead(field, offset=1, default=None)` | Value from N rows after |
| `FirstValue(field)` | First value in partition |
| `LastValue(field)` | Last value in partition |
| `NthValue(field, n)` | Value from the Nth row |

```python
from buraq.orm.window import Window, Lag, Lead, FirstValue

# Previous post's views
posts = await Post.objects.annotate_expr(
    prev_views=Window(Lag("views"), order_by="created_at")
).all()

# Next post's title
posts = await Post.objects.annotate_expr(
    next_title=Window(Lead("title", default=""), order_by="created_at")
).all()

# First post's title in each category
posts = await Post.objects.annotate_expr(
    first_title=Window(FirstValue("title"), partition_by="category_id", order_by="created_at")
).all()
```

## Combined with other annotations

Window functions compose with Q filters, ordering, and values:

```python
from buraq.orm.window import Window, DenseRank

# Top 3 posts per author by views
qs = await Post.objects.annotate_expr(
    rank=Window(DenseRank(), partition_by="author_id", order_by="-views")
).all()

top3 = [p for p in qs if p.rank <= 3]
```
