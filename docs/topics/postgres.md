# PostgreSQL

`buraq.contrib.postgres` provides PostgreSQL-specific fields, aggregates, and full-text search. Requires `asyncpg` driver:

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
