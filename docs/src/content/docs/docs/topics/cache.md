---
title: "Cache"
description: "Cache an entire view's response for a given number of seconds. Uses whatever backend is configured in CACHE_BACKEND."
---

## Configuration

```python title="config/settings.py"
# In-memory (default — single process only, resets on restart)
CACHE_BACKEND = "buraq.contrib.cache.backends.memory.MemoryCacheBackend"

# Redis (recommended for production)
# Requires: uv add "buraq[redis]"  or  pip install "buraq[redis]"
CACHE_BACKEND   = "buraq.contrib.cache.backends.redis.RedisCacheBackend"
CACHE_REDIS_URL = "redis://localhost:6379/0"

# Memcached
CACHE_BACKEND       = "buraq.contrib.cache.backends.memcached.MemcachedCacheBackend"
CACHE_MEMCACHED_URL = "memcached://localhost:11211"

# File
CACHE_BACKEND   = "buraq.contrib.cache.backends.file.FileCacheBackend"
CACHE_FILE_PATH = "/tmp/buraq_cache"

# Database — create the table once with: buraq createcachetable
CACHE_BACKEND          = "buraq.contrib.cache.backends.db.DatabaseCache"
CACHE_TABLE            = "buraq_cache_table"
CACHE_CULL_PROBABILITY = 0.1        # chance of evicting expired rows on write

# Shared options
CACHE_KEY_PREFIX      = "myapp:"   # prefix all keys to avoid collisions
CACHE_DEFAULT_TIMEOUT = 300        # default TTL in seconds
```

:::note
The database backend's table is created by `buraq createcachetable`, not by a
model, so migrations leave it alone — see
[what autogeneration ignores](/docs/topics/orm/migrations).
:::

## Basic usage

```python
from buraq.contrib.cache import cache


async def my_view(request):
    # Get
    value = await cache.get("my_key")

    # Set (timeout in seconds, None = no expiry)
    await cache.set("my_key", {"data": [1, 2, 3]}, timeout=300)

    # Delete
    await cache.delete("my_key")

    # Check existence
    exists = await cache.exists("my_key")

    # Get or set (atomic-ish)
    value = await cache.get_or_set("my_key", default_value, timeout=60)
    value = await cache.get_or_set("my_key", expensive_function, timeout=60)  # callable

    # Clear all
    await cache.clear()
```

## Atomic helpers

```python
# add — set only if key is not already present
was_set = await cache.add("lock:user:42", True, timeout=30)
if not was_set:
    return  # already locked

# incr / decr — atomic counter operations
await cache.set("page_views", 0)
views = await cache.incr("page_views")        # → 1
views = await cache.incr("page_views", delta=5)  # → 6
views = await cache.decr("page_views")        # → 5
```

## Sync access

For code that runs outside an async context (e.g. management commands, startup scripts):

```python
value = cache.get_sync("my_key")
cache.set_sync("my_key", value, timeout=300)
cache.delete_sync("my_key")
cache.delete_many_sync(["key1", "key2"])
cache.clear_sync()
```

## `@cache_page` decorator

Cache an entire view's response for a given number of seconds. Uses whatever backend is configured in `CACHE_BACKEND`.

```python
from buraq.decorators import cache_page


@cache_page(60 * 15)   # cache for 15 minutes
async def article_list(request):
    articles = await Article.objects.filter(is_published=True).order_by("-created_at")
    return await render(request, "articles/list.html", {"articles": articles})
```

The cache key is derived from the request method + path + query string. Only `200 OK` responses are cached.

Use a named cache backend or a custom key prefix:

```python
@cache_page(300, cache="redis", key_prefix="articles")
async def article_list(request):
    ...
```

## `@never_cache` decorator

```python
from buraq.decorators import never_cache

@never_cache
async def user_dashboard(request):
    # Response always has Cache-Control: no-store, Pragma: no-cache, Expires: 0
    ...
```

## `@cache_result` decorator

Cache the return value of **any async function** — not just views. Useful for expensive database queries or external API calls called from non-view code:

```python
from buraq.contrib.cache.decorators import cache_result

@cache_result(timeout=120)
async def get_top_posts(limit: int = 10):
    return await Post.objects.filter(is_published=True).order_by("-views").limit(limit).all()

# Second call within 120 s returns cached value — no DB query
posts = await get_top_posts(limit=5)
```

Provide an explicit key to share the cache entry across callers:

```python
@cache_result(key="global:stats", timeout=300)
async def site_stats():
    return await compute_expensive_stats()
```

When no key is given, one is auto-generated from the module + function name + argument hash.

## Batch operations

```python
# Get multiple keys
values = await cache.get_many(["key1", "key2", "key3"])
# → {"key1": ..., "key2": ..., "key3": ...}

# Set multiple keys
await cache.set_many({"key1": val1, "key2": val2}, timeout=300)

# Delete multiple keys
await cache.delete_many(["key1", "key2"])
```

## Caching in views

```python
async def post_detail(request, slug: str):
    cache_key = f"post:{slug}"
    post = await cache.get(cache_key)

    if post is None:
        post = await get_object_or_404(Post, slug=slug)
        await cache.set(cache_key, post, timeout=600)

    return await render(request, "posts/detail.html", {"post": post})
```

## Multi-cache `CACHES` dict

Configure multiple named backends the same way as Django's `CACHES` setting:

```python title="config/settings.py"
CACHES = {
    "default": {
        "BACKEND": "buraq.contrib.cache.backends.redis.RedisCacheBackend",
        "LOCATION": "redis://localhost:6379/0",
    },
    "sessions": {
        "BACKEND": "buraq.contrib.cache.backends.redis.RedisCacheBackend",
        "LOCATION": "redis://localhost:6379/1",
    },
    "views": {
        "BACKEND": "buraq.contrib.cache.backends.memory.MemoryCacheBackend",
    },
}
```

Access any backend by alias via the `caches` proxy:

```python
from buraq.contrib.cache import caches

await caches["default"].set("key", value)
await caches["sessions"].get("session:abc")
await caches["views"].clear()
```

`cache` (the default-backend shortcut) still works as before.

## `DatabaseCache` backend

Store cached values in a database table — no Redis or Memcached required:

```python title="config/settings.py"
CACHE_BACKEND = "buraq.contrib.cache.backends.db.DatabaseCache"
```

Create the table first:

```bash
python manage.py createcachetable
# or with a custom name:
python manage.py createcachetable --table my_cache
```

By default `DatabaseCache` automatically culls expired entries on ~10% of writes to prevent unbounded table growth. Tune or disable via `CACHE_CULL_PROBABILITY`:

```python title="config/settings.py"
CACHE_CULL_PROBABILITY = 0.05   # cull on 5% of writes (default 0.1)
CACHE_CULL_PROBABILITY = 0.0    # disable automatic culling
```

## `CacheMiddleware`

Full per-view response caching as middleware — caches all `GET`/`HEAD` responses automatically:

```python title="config/urls.py"
from buraq.middleware.cache import CacheMiddleware

app.add_middleware(CacheMiddleware, cache_timeout=300)
```

Use the layered pair for fine-grained control:

```python
from buraq.middleware.cache import FetchFromCacheMiddleware, UpdateCacheMiddleware

# Order matters — Starlette middleware is applied outermost-last
app.add_middleware(FetchFromCacheMiddleware)
app.add_middleware(UpdateCacheMiddleware, cache_timeout=300)
```

Use a named cache alias:

```python
app.add_middleware(CacheMiddleware, cache_timeout=600, cache_alias="views")
```

Responses with `Cache-Control: no-store`, `private`, or `no-cache` headers are never stored.

## `{% cache %}` template tag

Cache a block of template output for a given number of seconds. Rendered HTML is stored in the default cache backend — no DB or view involvement needed.

```html+jinja
{% cache 600 "sidebar" %}
  {# This block is rendered once, then cached for 10 minutes #}
  {% for item in get_popular_posts() %}
    <li>{{ item.title }}</li>
  {% endfor %}
{% endcache %}
```

The second argument is the **cache key** (a string literal). Make it unique per context when the content varies per user or URL:

```html+jinja
{% cache 300 "user-nav-" ~ request.user.id %}
  <nav>Hello, {{ request.user.username }}</nav>
{% endcache %}
```

Pass `0` to disable caching entirely (useful when `DEBUG = True`):

```html+jinja
{% cache 0 "nav" %}...{% endcache %}
```

The tag uses the default cache backend configured in `CACHE_BACKEND`. There is no way to select a named backend from the template — use `@cache_result` in a view helper if you need a specific backend.

---

## Backends

| Backend | Install | Best for |
|---|---|---|
| `MemoryCacheBackend` | built-in | Development, single-worker |
| `FileCacheBackend` | built-in | Small sites, dev |
| `RedisCacheBackend` | `uv add redis[hiredis]` | Production, multi-worker |
| `MemcachedCacheBackend` | `uv add aiomcache` | Production, high-throughput |
| `DatabaseCache` | built-in | Persistent cache, no extra service |
