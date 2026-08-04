# Sitemaps

Buraq's sitemap framework generates `sitemap.xml` files for search engines. It mirrors Django's `django.contrib.sitemaps` API and supports async querysets natively.

XML is generated using Python's stdlib `xml.etree.ElementTree` (C accelerator) — no extra dependencies.

---

## Usage

```python
from buraq.contrib.sitemaps import Sitemap, GenericSitemap
from buraq.contrib.sitemaps.views import sitemap
```

---

## Basic Sitemap

Subclass `Sitemap` and override `items()` and optionally `location()`, `lastmod()`, `changefreq`, and `priority`:

```python
# sitemaps.py
from buraq.contrib.sitemaps import Sitemap

class PostSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    async def items(self):
        return await Post.objects.filter(published=True)

    def location(self, post):
        return f"/posts/{post.slug}"

    def lastmod(self, post):
        return post.updated_at   # datetime or date — auto-formatted
```

Wire it up in `urls.py`:

```python
from buraq.urls import path
from buraq.contrib.sitemaps.views import sitemap
from myapp.sitemaps import PostSitemap
from functools import partial

sitemaps = {
    "posts": PostSitemap(),
}

urlpatterns = [
    path("/sitemap.xml", partial(sitemap, sitemaps=sitemaps)),
    # ... other urls
]
```

The sitemap is served at `/sitemap.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/posts/hello-world</loc>
    <lastmod>2026-08-04</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
</urlset>
```

---

## Multiple Sitemaps

Pass multiple sitemap objects to cover different sections of your site:

```python
# sitemaps.py
class PostSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    async def items(self):
        return await Post.objects.filter(published=True)

    def location(self, post):
        return f"/posts/{post.slug}"


class PageSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return ["/", "/about", "/contact"]

    def location(self, path):
        return path
```

```python
# urls.py
sitemaps = {
    "posts": PostSitemap(),
    "pages": PageSitemap(),
}

urlpatterns = [
    path("/sitemap.xml", partial(sitemap, sitemaps=sitemaps)),
]
```

---

## GenericSitemap

For quick sitemaps from a queryset — no subclassing needed:

```python
from buraq.contrib.sitemaps import GenericSitemap
from buraq.contrib.sitemaps.views import sitemap
from functools import partial

info_dict = {
    "queryset": Post.objects.filter(published=True),
    "date_field": "updated_at",   # used for <lastmod>
}

sitemaps = {
    "posts": GenericSitemap(info_dict, priority=0.6, changefreq="daily"),
}

urlpatterns = [
    path("/sitemap.xml", partial(sitemap, sitemaps=sitemaps)),
]
```

`GenericSitemap` calls `item.get_absolute_url()` for each item's location. Define it on your model:

```python
class Post(models.Model):
    slug = models.SlugField()

    def get_absolute_url(self):
        return f"/posts/{self.slug}"
```

---

## Dynamic changefreq and priority

Both `changefreq` and `priority` can be callables that receive the item:

```python
class PostSitemap(Sitemap):
    def changefreq(self, post):
        return "daily" if post.is_featured else "weekly"

    def priority(self, post):
        return 1.0 if post.is_featured else 0.6

    async def items(self):
        return await Post.objects.filter(published=True)

    def location(self, post):
        return f"/posts/{post.slug}"
```

---

## Sitemap Reference

### Sitemap class attributes

| Attribute | Default | Description |
|---|---|---|
| `changefreq` | `None` | `"always"`, `"hourly"`, `"daily"`, `"weekly"`, `"monthly"`, `"yearly"`, `"never"` — or a callable |
| `priority` | `None` | Float `0.0`–`1.0`, or a callable |
| `protocol` | `"https"` | URL scheme for absolute URLs |
| `limit` | `50000` | Max URLs per sitemap (sitemap protocol limit) |

### Sitemap methods

| Method | Returns | Description |
|---|---|---|
| `items()` | `list` or coroutine | Items to include — can be `async def` |
| `location(item)` | `str` | URL path for the item |
| `lastmod(item)` | `datetime \| date \| None` | Last modification time |
