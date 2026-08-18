---
title: "PostgreSQL"
description: "With CIEmailField, queries like filter(email=\"Alice@Example.COM\") match rows stored as alice@example.com."
---

`buraq.contrib.postgres` provides PostgreSQL-specific fields, aggregates, and full-text search. Requires the `asyncpg` driver (`uv add "buraq[postgres]"`):

```
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/mydb
```

## Fields

```python
from sqlalchemy import Column, Text
from buraq.contrib.postgres.fields import JSONField, ArrayField, HStoreField

class Article(Model):
    metadata   = Column(JSONField, default=dict)          # JSONB
    tags       = Column(ArrayField(Text), default=list)   # TEXT[]
    attributes = Column(HStoreField, default=dict)        # hstore
```

`HStoreField` requires the hstore extension:

```sql
CREATE EXTENSION IF NOT EXISTS hstore;
```

## Case-insensitive fields (citext)

```python
from buraq.contrib.postgres.fields import CITextField, CICharField, CIEmailField
from sqlalchemy import Column

class User(Model):
    username = Column(CICharField)   # case-insensitive VARCHAR (via CITEXT)
    email    = Column(CIEmailField)  # case-insensitive email
    bio      = Column(CITextField)   # case-insensitive TEXT
```

Requires the `citext` extension:

```sql
CREATE EXTENSION IF NOT EXISTS citext;
```

With `CIEmailField`, queries like `filter(email="Alice@Example.COM")` match rows stored as `alice@example.com`.

## Range fields

```python
from buraq.contrib.postgres.fields import (
    IntegerRangeField,
    BigIntegerRangeField,
    DecimalRangeField,
    DateRangeField,
    DateTimeRangeField,
)
from sqlalchemy import Column
from psycopg2.extras import NumericRange, DateRange, DateTimeTZRange

class Event(Model):
    seat_range  = Column(IntegerRangeField)      # int4range
    price_range = Column(DecimalRangeField)      # numrange
    date_range  = Column(DateRangeField)         # daterange
    time_range  = Column(DateTimeRangeField)     # tstzrange
```

## Advanced index types

```python
from buraq.contrib.postgres.fields import (
    GinIndex, GistIndex, BrinIndex,
    SpGistIndex, BloomIndex, HashIndex, TrgmIndex,
)

class Article(Model):
    class Meta:
        indexes = [
            GinIndex("tags_gin",       "tags"),            # JSONB / ARRAY
            GistIndex("loc_gist",      "location"),        # geometric / range
            BrinIndex("created_brin",  "created_at"),      # large, naturally ordered
            HashIndex("slug_hash",     "slug"),             # O(1) equality
            TrgmIndex("title_trgm",    "title"),            # trigram LIKE/ILIKE
        ]
```

## Trigram index (pg_trgm)

`TrgmIndex` enables fast `LIKE`, `ILIKE`, and similarity (`%`) queries on text columns.

```python
from buraq.contrib.postgres.fields import TrgmIndex

class Article(Model):
    title = models.CharField(max_length=300)
    body  = models.TextField()

    class Meta:
        indexes = [
            TrgmIndex("article_title_trgm", "title"),               # GIN (default)
            TrgmIndex("article_body_trgm",  "body", index_type="gist"),  # GiST variant
        ]
```

Requires the `pg_trgm` extension:

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

After creating the index, similarity searches become fast:

```python
# Fast ILIKE thanks to the trigram index
posts = await Article.objects.filter(title__icontains="buraq").all()
```

| `index_type` | Best for |
|---|---|
| `"gin"` (default) | `LIKE` / `ILIKE` pattern matching |
| `"gist"` | `ORDER BY similarity()` relevance ranking |

## Full-text search

### Filter by search query

```python
from buraq.contrib.postgres.search import SearchQuery

posts = await Post.objects.filter(
    SearchQuery("async python", field="body")
).all()
```

### Rank results by relevance

```python
from buraq.contrib.postgres.search import SearchRank

posts = await (
    Post.objects
    .annotate_expr(rank=SearchRank("body", "async python"))
    .order_by("-rank")
    .limit(10)
    .all()
)
```

### Search across multiple fields

```python
from buraq.contrib.postgres.search import SearchVector

posts = await Post.objects.filter(
    SearchQuery("buraq", field="title")
).all()
```

All search functions use `plainto_tsquery` — no special syntax needed from users, safe against injection.

## Aggregates

```python
from buraq.contrib.postgres.aggregates import ArrayAgg, StringAgg, JsonAgg

# Collect all tags into an array
result = await Post.objects.aggregate(all_tags=ArrayAgg("tag"))

# Comma-separated author names per category
result = await (
    Post.objects
    .values("category")
    .annotate(authors=StringAgg("author_name", delimiter=", "))
)

# JSON array of titles
result = await Post.objects.aggregate(titles=JsonAgg("title"))
```

### Bitwise aggregates

```python
from buraq.contrib.postgres.aggregates import BitAnd, BitOr, BoolAnd, BoolOr

# Bitwise AND / OR of an integer column
result = await Row.objects.aggregate(flags=BitAnd("flag_bits"))
result = await Row.objects.aggregate(flags=BitOr("flag_bits"))

# True if ALL rows have is_active=True
result = await User.objects.aggregate(all_active=BoolAnd("is_active"))

# True if ANY row has is_admin=True
result = await User.objects.aggregate(any_admin=BoolOr("is_admin"))
```

| Aggregate | Description |
|---|---|
| `BitAnd(field)` | Bitwise AND across all non-null integers |
| `BitOr(field)` | Bitwise OR across all non-null integers |
| `BoolAnd(field)` | `True` if all values are true |
| `BoolOr(field)` | `True` if any value is true |

### Statistical aggregates

```python
from buraq.contrib.postgres.aggregates import (
    Corr, CovarPop, CovarSamp,
    RegrSlope, RegrIntercept, RegrR2, RegrCount,
    RegrAvgX, RegrAvgY, RegrSXX, RegrSXY, RegrSYY,
)

# Pearson correlation of price vs. rating
result = await Product.objects.aggregate(
    r=Corr("price", "rating")
)

# Least-squares regression: slope and intercept
result = await Sale.objects.aggregate(
    slope=RegrSlope("revenue", "units"),
    intercept=RegrIntercept("revenue", "units"),
    r2=RegrR2("revenue", "units"),
)
```

All statistical aggregates take `(y_field, x_field)` positional arguments — `y` is the dependent variable, `x` the independent variable.

| Aggregate | Description |
|---|---|
| `Corr(y, x)` | Pearson correlation coefficient |
| `CovarPop(y, x)` | Population covariance |
| `CovarSamp(y, x)` | Sample covariance |
| `RegrAvgX(y, x)` | Average of `x` |
| `RegrAvgY(y, x)` | Average of `y` |
| `RegrCount(y, x)` | Rows where both non-null |
| `RegrIntercept(y, x)` | Y-intercept of least-squares line |
| `RegrR2(y, x)` | R² (coefficient of determination) |
| `RegrSlope(y, x)` | Slope of least-squares line |
| `RegrSXX(y, x)` | Σ(x − x̄)² |
| `RegrSXY(y, x)` | Σ(x − x̄)(y − ȳ) |
| `RegrSYY(y, x)` | Σ(y − ȳ)² |

## Functions

```python
from buraq.contrib.postgres.functions import Unaccent, Random

# Search without accent sensitivity (requires unaccent extension)
posts = await Post.objects.annotate_expr(
    clean_title=Unaccent("title")
).all()

# Random ordering
posts = await Post.objects.annotate_expr(rand=Random()).order_by("rand").all()
```
