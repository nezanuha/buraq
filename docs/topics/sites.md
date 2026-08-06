# Sites

`buraq.contrib.sites` lets a single Buraq installation serve multiple domains, with per-domain configuration.

## Setup

```python
INSTALLED_APPS = ["buraq.contrib.sites", ...]
```

## Creating sites

```python
from buraq.contrib.sites.models import Site

await Site.objects.create(domain="example.com", name="Example")
await Site.objects.create(domain="staging.example.com", name="Staging")
```

## Getting the current site

```python
from buraq.contrib.sites.models import Site

async def my_view(request):
    site = await Site.get_current(request)
    # Matches request Host header to site domain
    # Falls back to first site if no match
    return templates.TemplateResponse(request, "home.html", {"site": site})
```

## Using in templates

```html
<title>{{ site.name }}</title>
<meta property="og:url" content="https://{{ site.domain }}{{ request.url.path }}">
```

## Common patterns

**Per-site content:**

```python
class Article(Model):
    site_id = Column(Integer, ForeignKey("sites_site.id"))
    title = Column(String(255))

# Filter by current site
site = await Site.get_current(request)
articles = await Article.objects.filter(site_id=site.id).all()
```

**Absolute URLs:**

```python
site = await Site.get_current(request)
absolute_url = f"https://{site.domain}/posts/{post.slug}"
```
