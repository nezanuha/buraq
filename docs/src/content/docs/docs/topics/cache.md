---
title: "Cache"
description: "Store values in Redis, memcached, files, the database or memory, and cache whole responses or parts of a page."
---

## Configuration

One URL says which backend and where, the way `DATABASE_URL` does:

```python title="config/settings.py"
CACHE_URL = "redis://localhost:6379/0"
```

| `CACHE_URL` | Backend | Install |
| --- | --- | --- |
| *(unset)* | in-process memory — the default | — |
| `locmem://` | in-process memory | — |
| `redis://host:6379/0` | Redis | `pip install "buraq[redis]"` |
| `rediss://user:pw@host:6380/0` | Redis over TLS | `pip install "buraq[redis]"` |
| `memcached://host:11211` | Memcached | `pip install "buraq[memcached]"` |
| `file:///var/tmp/cache` | files on disk | — |
| `db://buraq_cache_table` | a database table | `buraq createcachetable` |

For more than one memcached server, separate them with commas:
`memcached://a:11211,b:11211`. An unknown scheme is refused when the application
starts, naming the ones that exist; `parse_cache_url()` is what reads it, if you
want to check what a given URL resolves to.

Two settings apply whatever the backend:

```python title="config/settings.py"
CACHE_KEY_PREFIX      = "myapp:"   # prefix every key, to share a store safely
CACHE_DEFAULT_TIMEOUT = 300        # seconds, when set() is given no timeout
```

### Several caches

Name them, and reach one with `caches["alias"]`:

```python title="config/settings.py"
REDIS = "buraq.contrib.cache.backends.redis.RedisCacheBackend"

CACHES = {
    "default":  {"BACKEND": REDIS, "LOCATION": "redis://localhost:6379/0",
                 "KEY_PREFIX": "app:",  "TIMEOUT": 300},
    "sessions": {"BACKEND": REDIS, "LOCATION": "redis://localhost:6379/0",
                 "KEY_PREFIX": "sess:", "TIMEOUT": 1209600},
    "views":    {"BACKEND": "buraq.contrib.cache.backends.memory.MemoryCacheBackend"},
}
```

```python
from buraq.contrib.cache import caches

await caches["sessions"].set("key", value)
await caches["views"].clear()
```

`cache` remains a shortcut for `caches["default"]`.

`LOCATION` means what it does in Django, which differs by backend: the server
for Redis and memcached, the directory for the file cache, the table for the
database cache, and a name for the in-process one. `TIMEOUT` and `KEY_PREFIX`
override the settings above for that cache alone — two caches can share one
Redis database as long as their prefixes differ. Anything else a backend accepts
goes in `OPTIONS`, such as `{"OPTIONS": {"max_size": 5000}}`.

Any other key in an entry is refused at startup rather than ignored: a setting
that silently does nothing is discovered in production.

:::note[Porting a Django `CACHES` dict]
The keys mean the same things, so a Django entry usually needs only its
`BACKEND` path changed to Buraq's. `MAX_ENTRIES` in `OPTIONS` is understood as
Buraq's `max_size`.

Two Django keys have no equivalent here and are refused rather than ignored:
`VERSION` (Buraq does not version keys) and `KEY_FUNCTION` (keys are built from
`KEY_PREFIX` alone). An option a backend does not accept is refused too, naming
the ones it does.
:::

`CACHES` takes precedence over `CACHE_URL`, which takes precedence over
`CACHE_BACKEND`.

<details>
<summary>Per-backend settings (older style)</summary>

`CACHE_URL` replaced these, and they still work. Each is read only by the
backend it belongs to, which is why one URL is easier to get right.

```python title="config/settings.py"
CACHE_BACKEND = "buraq.contrib.cache.backends.redis.RedisCacheBackend"

CACHE_REDIS_URL         = "redis://localhost:6379/0"
CACHE_MEMCACHED_URL     = "memcached://localhost:11211"
CACHE_MEMCACHED_SERVERS = [("cache1", 11211), ("cache2", 11211)]  # wins over the URL
CACHE_FILE_PATH         = "/tmp/buraq_cache"
CACHE_TABLE             = "buraq_cache_table"
CACHE_CULL_PROBABILITY  = 0.1   # chance of evicting expired rows on write
```

</details>

:::note[Entries expire by default]
`cache.set(key, value)` with no timeout uses `CACHE_DEFAULT_TIMEOUT`, which is
`300` seconds unless you change it. Pass `timeout=0` for an entry that should
never expire.

This was not always so: Redis, in-memory and file entries used to be written
with no expiry at all whatever the setting said, and the database backend used a
hardcoded 300 seconds. If a project relied on cached values persisting
indefinitely, set `CACHE_DEFAULT_TIMEOUT = 0` or pass `timeout=0` explicitly.
:::

:::note
The database backend's table is created by `buraq createcachetable`, not by a
model, so migrations leave it alone — see
[what autogeneration ignores](/docs/topics/orm/migrations).
:::

## Using the cache

### Reading and writing

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

### Several keys at once

```python
# Get multiple keys
values = await cache.get_many(["key1", "key2", "key3"])
# → {"key1": ..., "key2": ..., "key3": ...}

# Set multiple keys
await cache.set_many({"key1": val1, "key2": val2}, timeout=300)

# Delete multiple keys
await cache.delete_many(["key1", "key2"])
```

### Atomic helpers

```python
# add — set only if key is not already present
was_set = await cache.add("lock:user:42", True, timeout=30)
if not was_set:
    return  # already locked

# incr / decr — counter operations
await cache.set("page_views", 0)
views = await cache.incr("page_views")        # → 1
views = await cache.incr("page_views", delta=5)  # → 6
views = await cache.decr("page_views")        # → 5
```

:::note[Entries expire by default]
`cache.set(key, value)` with no timeout uses `CACHE_DEFAULT_TIMEOUT`, which is
`300` seconds unless you change it. Pass `timeout=0` for an entry that should
never expire.

This was not always so: Redis, in-memory and file entries used to be written
with no expiry at all whatever the setting said, and the database backend used
a hardcoded 300 seconds. If a project relied on cached values persisting
indefinitely, set `CACHE_DEFAULT_TIMEOUT = 0` or pass `timeout=0` explicitly.
:::

:::caution[`add` and `incr` are atomic on Redis and in memory only]
Both are one operation on the Redis backend (`SET NX` and `INCRBY`) and are held
under a lock in the in-memory one, so concurrent callers cannot interleave.

The memcached, database and file backends inherit a read-then-write
implementation, and both calls suspend there: concurrent callers all read the
same value and all write back the same result. Measured against a backend that
suspends, 500 concurrent `incr` calls landed as **1**. Use `add` as a lock, or
`incr` as a counter you can trust, only on Redis or in memory.
:::

### Sync access

For code that runs outside an async context (e.g. management commands, startup scripts):

```python
value = cache.get_sync("my_key")
cache.set_sync("my_key", value, timeout=300)
cache.delete_sync("my_key")
cache.delete_many_sync(["key1", "key2"])
cache.clear_sync()
```

## Caching responses

### `@cache_page`

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

### `@never_cache`

```python
from buraq.decorators import never_cache

@never_cache
async def user_dashboard(request):
    # Response always has Cache-Control: no-store, Pragma: no-cache, Expires: 0
    ...
```

### `@cache_result`, for a function's return value

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

### Reaching the cache from a view

```python
async def post_detail(request, slug: str):
    cache_key = f"post:{slug}"
    post = await cache.get(cache_key)

    if post is None:
        post = await get_object_or_404(Post, slug=slug)
        await cache.set(cache_key, post, timeout=600)

    return await render(request, "posts/detail.html", {"post": post})
```

### `CacheMiddleware`, for the whole site

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

### `{% cache %}`, for part of a page

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

### `DatabaseCache`

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

### What each backend can store

Backends do not all serialize the same way, and the difference decides both what
you can cache and how much you must trust the store.

| Backend | Serialization | Can store |
|---|---|---|
| `MemoryCacheBackend` | none — the object itself | anything |
| `FileCacheBackend` | JSON | JSON-serializable values |
| `RedisCacheBackend` | JSON | JSON-serializable values |
| `DatabaseCache` | pickle | any picklable object |
| `MemcachedCacheBackend` | pickle | any picklable object |

Caching a model instance or a `datetime` works on the pickle backends. The JSON
backends raise `TypeError` naming the value and the key, so cache `post.id` or an
ISO string instead:

```python
await cache.set("created", post.created_at)          # TypeError on JSON backends
await cache.set("created", post.created_at.isoformat())   # fine everywhere
```

:::danger[A pickle cache must be as trusted as your application]
`DatabaseCache` and `MemcachedCacheBackend` call `pickle.loads` on whatever they
read back. Unpickling runs code by design, so anyone able to write to that table
or Memcached instance can run code in your application — no exploit needed, that
is what the format does.

In practice this means:

- Never point them at a Memcached instance reachable from outside your network.
  Memcached has no authentication.
- Never share the cache table or Memcached instance with anything less trusted
  than the application itself.
- Prefer `RedisCacheBackend` where the values you cache are JSON-serializable;
  it reads back with `json.loads`, which cannot execute anything.

This is the same trade-off Django makes for the same reason, and it is safe
under the assumption above. It stops being safe the moment the store is shared
or exposed.
:::
