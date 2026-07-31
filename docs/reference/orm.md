# buraq.orm — API Reference

## Model

Base class for all models. Import from `buraq`:

```python
from buraq import models

class Post(models.Model):
    ...
```

### Class attributes

| Attribute | Description |
|---|---|
| `objects` | The default `Manager` for this model |
| `__table__` | The underlying SQLAlchemy `Table` |
| `__tablename__` | The database table name |

### Instance methods

| Method | Description |
|---|---|
| `await instance.save()` | Insert or update this instance |
| `await instance.delete()` | Delete this instance |

---

## Manager

Accessed via `Model.objects`.

```python
# All methods are async and must be awaited
await Post.objects.all()
await Post.objects.filter(**kwargs)
await Post.objects.exclude(**kwargs)
await Post.objects.get(**kwargs)
await Post.objects.get_or_none(**kwargs)
await Post.objects.create(**kwargs)
await Post.objects.count()
await Post.objects.exists()
await Post.objects.bulk_create(records, ignore_conflicts=False)
```

### QuerySet methods (chainable)

```python
qs = Post.objects.filter(is_published=True)
qs = qs.order_by("-created_at")
qs = qs.limit(10).offset(20)
# Evaluate:
posts = await qs
```

---

## Q — Complex filters

```python
from buraq.orm.query import Q

Q(field=value)              # equality
Q(field__lookup=value)      # lookup
Q1 & Q2                     # AND
Q1 | Q2                     # OR
~Q1                         # NOT
```

### Supported lookups

`eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `contains`, `icontains`, `startswith`,
`istartswith`, `endswith`, `iendswith`, `in`, `isnull`, `year`, `month`, `day`

---

## F — Field references

```python
from buraq.orm.query import F

# Increment without read-modify-write
await Post.objects.filter(id=1).update(views=F("views") + 1)

# Compare fields
await Post.objects.filter(updated_at__gt=F("created_at"))
```

---

## Paginator

```python
from buraq.paginator import Paginator

paginator = Paginator(queryset, per_page=10)
page      = await paginator.page(page_number)

page.object_list          # items on this page
page.number               # current page number
page.has_next()           # bool
page.has_previous()       # bool
page.next_page_number()   # int
page.previous_page_number()
paginator.num_pages       # total pages
paginator.count           # total items
```
