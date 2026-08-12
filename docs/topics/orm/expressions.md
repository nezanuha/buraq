# ORM Expressions

Expressions let you build conditional logic, subqueries, and window functions directly in your ORM queries.

---

## Case / When

Conditional expressions — equivalent to SQL `CASE WHEN … THEN … END`.

```python
from buraq.orm.expressions import Case, When, Value

posts = await Post.objects.annotate(
    status_label=Case(
        When(status="published", then=Value("Live")),
        When(status="draft",     then=Value("Draft")),
        default=Value("Unknown"),
    )
)
# Each post gets a status_label attribute
```

Use `Q` objects or field lookups in `When` conditions:

```python
from buraq.orm.query import Q
from buraq.orm.expressions import Case, When, Value

result = await Order.objects.annotate(
    priority=Case(
        When(Q(total__gte=1000) & Q(is_vip=True), then=Value("high")),
        When(total__gte=500, then=Value("medium")),
        default=Value("low"),
    )
)
```

---

## Subquery

Embed a correlated subquery as an annotation.

```python
from buraq.orm.expressions import Subquery, OuterRef
from buraq.orm.aggregates import Count

# Count comments per post in a single query
comment_count = Subquery(
    Comment.objects.filter(post_id=OuterRef("id"))
    .values("id")
    .annotate(n=Count("id"))
    .values("n")
)

posts = await Post.objects.annotate(comment_count=comment_count)
```

`OuterRef("field")` references a column on the outer query model.

---

## Exists

Filter based on whether a related subquery has any rows.

```python
from buraq.orm.expressions import Exists, OuterRef

has_comments = Exists(Comment.objects.filter(post_id=OuterRef("id")))

# Only posts that have at least one comment
posts = await Post.objects.filter(has_comments=has_comments)
```

---

## ExpressionWrapper

Wrap an F expression or SQLAlchemy expression and assign it an output type.

```python
from buraq.orm.expressions import ExpressionWrapper
from buraq.orm.query import F

revenue = ExpressionWrapper(F("price") * F("quantity"), output_field="decimal")
orders = await Order.objects.annotate(revenue=revenue)
```

---

## JSONNull

Use `JSONNull` to store an explicit JSON `null` value in a JSON column. SQL `NULL` and JSON `null` are distinct concepts — `JSONNull` renders as `CAST(NULL AS JSON)` so the database stores the JSON scalar rather than a missing value.

```python
from buraq.orm.expressions import JSONNull

await Post.objects.filter(id=1).update(metadata=JSONNull())
# SQL: UPDATE post SET metadata = CAST(NULL AS JSON) WHERE id = 1
```

Use it in annotations to distinguish "no value" from "the value is JSON null":

```python
from buraq.orm.expressions import Case, When, JSONNull, Value

posts = await Post.objects.annotate(
    payload=Case(
        When(archived=True, then=JSONNull()),
        default=Value({"active": True}),
    )
)
```

---

## Window Functions

Compute running totals, ranks, and moving averages without a GROUP BY.

```python
from buraq.orm.window import Window, RowNumber, Rank, Lag

# Rank posts by score within each category
posts = await Post.objects.annotate(
    rank=Window(Rank(), partition_by="category_id", order_by="-score")
)

# Row number per author
posts = await Post.objects.annotate(
    row_num=Window(RowNumber(), partition_by="author_id", order_by="created_at")
)

# Previous post's score (Lag)
posts = await Post.objects.annotate(
    prev_score=Window(Lag("score", offset=1, default=0), order_by="created_at")
)
```

### Available window functions

| Function | Description |
|---|---|
| `RowNumber()` | Sequential row number |
| `Rank()` | Rank with gaps |
| `DenseRank()` | Rank without gaps |
| `PercentRank()` | Relative rank (0–1) |
| `CumeDist()` | Cumulative distribution |
| `Ntile(n)` | Divide rows into n buckets |
| `Lag(field, offset, default)` | Value from a previous row |
| `Lead(field, offset, default)` | Value from a following row |
| `FirstValue(field)` | First value in the window |
| `LastValue(field)` | Last value in the window |
| `NthValue(field, n)` | Nth value in the window |

### Window parameters

```python
Window(
    expression,           # required — one of the functions above
    partition_by=None,    # str or list of str field names
    order_by=None,        # str or list, prefix "-" for descending
)
```
