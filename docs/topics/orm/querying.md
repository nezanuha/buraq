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
