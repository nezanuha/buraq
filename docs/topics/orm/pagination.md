# Pagination

`Paginator` splits a queryset or list into fixed-size pages.

```python
from buraq.paginator import Paginator
```

## Basic usage

```python
paginator = Paginator(Post.objects.filter(is_published=True), per_page=10)
page = await paginator.page(1)

for post in page:
    print(post.title)

print(paginator.count)      # total objects across all pages
print(paginator.num_pages)  # total number of pages
print(page.number)          # current page number (1-based)
```

## Page navigation

```python
page = await paginator.page(2)

page.has_previous()         # True
page.has_next()             # True / False
page.has_other_pages()      # True if there is any adjacent page

page.previous_page_number() # 1
page.next_page_number()     # 3

page.start_index()          # 1-based index of first item on this page
page.end_index()            # 1-based index of last item on this page
```

## Page range

Iterate over all page numbers (useful for rendering page links):

```python
for page_num in paginator.page_range:   # range(1, num_pages + 1)
    print(page_num)
```

## In a view

```python
from buraq.paginator import Paginator, EmptyPage, PageNotAnInteger

async def post_list(request):
    page_number = request.query_params.get("page", 1)
    paginator = Paginator(Post.objects.all(), per_page=20)

    try:
        page = await paginator.page(page_number)
    except PageNotAnInteger:
        page = await paginator.page(1)
    except EmptyPage:
        page = await paginator.page(paginator.num_pages)

    return templates.TemplateResponse(request, "posts/list.html", {"page": page})
```

Template:

```html
{% for post in page %}
  <h2>{{ post.title }}</h2>
{% endfor %}

{% if page.has_previous() %}
  <a href="?page={{ page.previous_page_number() }}">Previous</a>
{% endif %}

Page {{ page.number }} of {{ page.paginator.num_pages }}

{% if page.has_next() %}
  <a href="?page={{ page.next_page_number() }}">Next</a>
{% endif %}
```

## Paginating plain lists

`Paginator` works with any sequence, not just querysets:

```python
items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
paginator = Paginator(items, per_page=3)
page = await paginator.page(2)
list(page)   # [4, 5, 6]
```

## Options

```python
Paginator(
    object_list,
    per_page=10,
    orphans=0,                  # if last page has ≤ orphans items, merge into previous page
    allow_empty_first_page=True # allow page 1 even when there are no objects
)
```

## Exceptions

| Exception | Raised when |
|---|---|
| `PageNotAnInteger` | Page number cannot be converted to an integer |
| `EmptyPage` | Page number is out of range |
| `InvalidPage` | Base class for the above two |
