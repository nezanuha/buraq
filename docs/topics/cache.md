# Cache

## Configuration

```python title="config/settings.py"
# In-memory (default — single process only, resets on restart)
CACHE_BACKEND = "buraq.contrib.cache.backends.memory.MemoryCacheBackend"

# Redis (recommended for production)
CACHE_BACKEND   = "buraq.contrib.cache.backends.redis.RedisCacheBackend"
CACHE_REDIS_URL = "redis://localhost:6379/0"

# Memcached
CACHE_BACKEND       = "buraq.contrib.cache.backends.memcached.MemcachedCacheBackend"
CACHE_MEMCACHED_URL = "memcached://localhost:11211"

# File
CACHE_BACKEND   = "buraq.contrib.cache.backends.file.FileCacheBackend"
CACHE_FILE_PATH = "/tmp/buraq_cache"

# Shared options
CACHE_KEY_PREFIX      = "myapp:"   # prefix all keys to avoid collisions
CACHE_DEFAULT_TIMEOUT = 300        # default TTL in seconds
```

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

## `never_cache` decorator

```python
from buraq.decorators import never_cache

@never_cache
async def user_dashboard(request):
    # Response always has Cache-Control: no-store, Pragma: no-cache, Expires: 0
    ...
```

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

    return render(request, "posts/detail.html", {"post": post})
```

## Backends

| Backend | Install | Best for |
|---|---|---|
| `MemoryCacheBackend` | built-in | Development, single-worker |
| `FileCacheBackend` | built-in | Small sites, dev |
| `RedisCacheBackend` | `uv add redis[hiredis]` | Production, multi-worker |
| `MemcachedCacheBackend` | `uv add aiomcache` | Production, high-throughput |
