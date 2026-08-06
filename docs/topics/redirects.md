# Redirects

`buraq.contrib.redirects` provides database-driven URL redirects — change where a URL points without redeploying.

## Setup

```python
INSTALLED_APPS = ["buraq.contrib.redirects", ...]
```

Add the middleware **after** your router so it catches 404s:

```python
from buraq.contrib.redirects.middleware import RedirectFallbackMiddleware

app.add_middleware(RedirectFallbackMiddleware)
```

## Creating redirects

```python
from buraq.contrib.redirects.models import Redirect

# 301 permanent redirect
await Redirect.objects.create(old_path="/old-page", new_path="/new-page")

# 410 Gone (leave new_path empty)
await Redirect.objects.create(old_path="/deleted-page", new_path="")
```

## How it works

1. A request comes in for `/old-page`
2. Your router returns 404
3. `RedirectFallbackMiddleware` intercepts the 404
4. It looks up `/old-page` in the `redirects_redirect` table
5. If found: returns 301 to `new_path`, or 410 if `new_path` is empty
6. If not found: lets the 404 pass through

## Bulk redirect management

```python
redirects = [
    {"old_path": "/blog/post-1", "new_path": "/posts/post-1"},
    {"old_path": "/blog/post-2", "new_path": "/posts/post-2"},
]
await Redirect.objects.bulk_create(redirects, ignore_conflicts=True)
```
