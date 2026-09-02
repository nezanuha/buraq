"""
One URL for the cache, the way ``DATABASE_URL`` is one URL for the database.

Configuring a cache took a backend path plus whichever of six settings that
backend happened to read -- ``CACHE_REDIS_URL``, ``CACHE_MEMCACHED_URL``,
``CACHE_MEMCACHED_SERVERS``, ``CACHE_FILE_PATH``, ``CACHE_TABLE``. Most of them
are meaningless for any given backend, and nothing in a settings file said which
ones were live, so the same address could be written twice and only one of them
read.

``CACHE_URL = "redis://localhost:6379/0"`` says both things at once: the scheme
picks the backend, the rest configures it. It is the shape the project already
uses for the database, and the shape a container hands an application in an
environment variable.
"""
from __future__ import annotations

from urllib.parse import urlparse

from buraq.exceptions import ImproperlyConfigured

__all__ = ["parse_cache_url", "SCHEMES"]

_BACKENDS = "buraq.contrib.cache.backends"

#: Scheme -> the backend it names. Aliases are listed so that a URL copied from
#: elsewhere -- a Heroku config var, a docker-compose file -- works as written.
SCHEMES: dict[str, str] = {
    "locmem": f"{_BACKENDS}.memory.MemoryCacheBackend",
    "memory": f"{_BACKENDS}.memory.MemoryCacheBackend",
    "redis": f"{_BACKENDS}.redis.RedisCacheBackend",
    "rediss": f"{_BACKENDS}.redis.RedisCacheBackend",
    "memcached": f"{_BACKENDS}.memcached.MemcachedCacheBackend",
    "memcache": f"{_BACKENDS}.memcached.MemcachedCacheBackend",
    "file": f"{_BACKENDS}.file.FileCacheBackend",
    "db": f"{_BACKENDS}.db.DatabaseCache",
    "database": f"{_BACKENDS}.db.DatabaseCache",
}


def parse_cache_url(url: str) -> tuple[str, dict]:
    """Turn a cache URL into ``(backend path, keyword arguments)``.

    ``redis://host:6379/0``   -> the Redis backend, pointed at that server
    ``memcached://host:11211`` -> memcached, likewise
    ``file:///var/tmp/cache``  -> the file backend, in that directory
    ``db://my_cache_table``    -> the database backend, in that table
    ``locmem://``              -> the in-process backend
    """
    if not isinstance(url, str) or not url.strip():
        raise ImproperlyConfigured(
            "CACHE_URL is empty. It looks like 'redis://localhost:6379/0'."
        )

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if not scheme:
        raise ImproperlyConfigured(
            f"CACHE_URL = {url!r} has no scheme. The scheme is what picks the "
            f"backend: {', '.join(sorted(SCHEMES))}."
        )
    if scheme not in SCHEMES:
        raise ImproperlyConfigured(
            f"CACHE_URL = {url!r} names no cache Buraq has. Use one of: "
            f"{', '.join(sorted(SCHEMES))}."
        )

    backend = SCHEMES[scheme]
    options: dict = {}

    if scheme in ("redis", "rediss"):
        # Handed on whole -- the client understands passwords, TLS and database
        # numbers, and re-assembling it here would only lose parts of it.
        options["url"] = url
    elif scheme in ("memcached", "memcache"):
        # "memcached://a:11211,b:11211" for more than one server.
        servers = url.split("://", 1)[1]
        options["location"] = [s for s in servers.split(",") if s] or None
    elif scheme == "file":
        # file:///var/tmp/cache -> /var/tmp/cache, and file://./cache -> ./cache
        path = f"{parsed.netloc}{parsed.path}"
        if not path:
            raise ImproperlyConfigured(
                f"CACHE_URL = {url!r} names no directory. Write it as "
                f"'file:///var/tmp/cache'."
            )
        options["cache_dir"] = path
    elif scheme in ("db", "database"):
        # db://table_name -- the table is the only thing to say, since the
        # connection is DATABASE_URL's business.
        table = parsed.netloc or parsed.path.lstrip("/")
        if table:
            options["table"] = table

    return backend, options
