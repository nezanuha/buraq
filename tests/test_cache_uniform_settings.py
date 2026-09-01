"""
Every backend has to mean the same thing by a timeout and a key prefix.

They did not. `cache.set(key, value)` with no timeout did four different things:

    Redis     never expired
    memory    never expired
    file      never expired
    database  expired after a hardcoded 300s
    memcached expired after CACHE_DEFAULT_TIMEOUT   <- the only one that read it

So CACHE_DEFAULT_TIMEOUT did nothing on four backends out of five, and a Redis
cache grew until it evicted or died. CACHE_KEY_PREFIX had the mirror problem --
honoured by Redis and memcached, ignored by the other three -- so a prefix
keeping two environments apart in one store silently stopped keeping them apart
if the backend changed.

The shared behaviour now lives on BaseCacheBackend, so a backend cannot quietly
opt out of it.
"""

import tempfile

import pytest

from buraq.conf import settings
from buraq.contrib.cache.backends.db import DatabaseCache
from buraq.contrib.cache.backends.file import FileCacheBackend
from buraq.contrib.cache.backends.memcached import MemcachedCacheBackend
from buraq.contrib.cache.backends.memory import MemoryCacheBackend
from buraq.contrib.cache.backends.redis import RedisCacheBackend


def _every_backend():
    return [
        ("memory", MemoryCacheBackend()),
        ("file", FileCacheBackend(cache_dir=tempfile.mkdtemp())),
        ("redis", RedisCacheBackend()),
        ("database", DatabaseCache()),
        ("memcached", MemcachedCacheBackend()),
    ]


@pytest.fixture
async def cache_table():
    """The database cache's table is made by `buraq createcachetable`, not by a
    migration, so a test that uses it has to create it."""
    import sqlalchemy as sa

    from buraq.core.db import SessionLocal

    async with SessionLocal() as db:
        await db.execute(sa.text("DROP TABLE IF EXISTS buraq_cache_table"))
        await db.execute(
            sa.text(
                "CREATE TABLE buraq_cache_table ("
                "cache_key VARCHAR(255) NOT NULL PRIMARY KEY, "
                "value TEXT NOT NULL, "
                "expires DOUBLE PRECISION NOT NULL)"
            )
        )
        await db.commit()
    yield
    async with SessionLocal() as db:
        await db.execute(sa.text("DROP TABLE IF EXISTS buraq_cache_table"))
        await db.commit()


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    monkeypatch.setattr(settings, "CACHE_DEFAULT_TIMEOUT", 300, raising=False)
    monkeypatch.setattr(settings, "CACHE_KEY_PREFIX", "app:", raising=False)
    monkeypatch.setattr(settings, "CACHE_VERSION", 1, raising=False)


def test_every_backend_reads_the_default_timeout():
    for name, backend in _every_backend():
        assert backend._default_timeout == 300, f"{name} ignores CACHE_DEFAULT_TIMEOUT"


def test_every_backend_reads_the_key_prefix():
    """Necessary but not sufficient -- see the test below, which is the one that
    would have caught the database backend storing the prefix and never using
    it."""
    for name, backend in _every_backend():
        assert backend._prefix == "app:", f"{name} ignores CACHE_KEY_PREFIX"


@pytest.mark.asyncio
@pytest.mark.parametrize("make", ["memory", "file", "database"])
async def test_two_prefixes_do_not_see_each_other(make, tmp_path, cache_table):
    """
    Reading the setting is not the same as applying it. The database backend
    stored `_prefix` and built every statement with the raw key, so
    CACHE_KEY_PREFIX did nothing there -- and the test above, which only checked
    the attribute, passed the whole time.

    This is the property the prefix exists for, and it cannot pass unless the
    backend actually uses it.
    """
    if make == "memory":
        one, two = MemoryCacheBackend(key_prefix="a:"), MemoryCacheBackend(key_prefix="b:")
    elif make == "file":
        shared = str(tmp_path / "cache")
        one = FileCacheBackend(cache_dir=shared, key_prefix="a:")
        two = FileCacheBackend(cache_dir=shared, key_prefix="b:")
    else:
        one, two = DatabaseCache(key_prefix="a:"), DatabaseCache(key_prefix="b:")

    await one.set("user:42", "from a")
    await two.set("user:42", "from b")

    assert await one.get("user:42") == "from a"
    assert await two.get("user:42") == "from b"


@pytest.mark.asyncio
async def test_clearing_one_prefix_leaves_the_other(cache_table):
    """Two caches in one table must not wipe each other."""
    one, two = DatabaseCache(key_prefix="a:"), DatabaseCache(key_prefix="b:")
    await one.set("k", "from a")
    await two.set("k", "from b")

    await one.clear()

    assert await one.get("k") is None
    assert await two.get("k") == "from b"


def test_a_cache_entry_expires_by_default():
    """The bug this exists for: an entry written with no timeout used to live
    forever on three of the five backends. A cache that never evicts is a
    memory leak with a lookup method."""
    for name, backend in _every_backend():
        assert backend._resolve_timeout(None) == 300, f"{name} would never expire it"


def test_an_explicit_timeout_wins():
    for name, backend in _every_backend():
        assert backend._resolve_timeout(60) == 60, name


def test_a_timeout_of_zero_is_kept_as_zero():
    """Zero means "never expire", asked for deliberately. It must not be
    mistaken for "nothing was passed" and replaced by the default."""
    for name, backend in _every_backend():
        assert backend._resolve_timeout(0) == 0, name


def test_a_per_cache_timeout_overrides_the_setting():
    backend = MemoryCacheBackend(timeout=30)
    assert backend._default_timeout == 30


def test_a_per_cache_prefix_overrides_the_setting():
    backend = MemoryCacheBackend(key_prefix="sess:")
    assert backend._prefix == "sess:"


def test_a_per_cache_prefix_of_empty_string_is_respected():
    """Asking for no prefix is a decision, not a missing value."""
    assert MemoryCacheBackend(key_prefix="")._prefix == ""


# --- the prefix actually reaching the store ---------------------------------


@pytest.mark.asyncio
async def test_the_prefix_is_applied_to_stored_keys():
    backend = MemoryCacheBackend()
    await backend.set("k", "v")
    assert list(backend._store) == ["app:1:k"], "prefix, version, then the key"


@pytest.mark.asyncio
async def test_a_prefixed_key_reads_back():
    backend = MemoryCacheBackend()
    await backend.set("k", "v")
    assert await backend.get("k") == "v"


@pytest.mark.asyncio
async def test_two_caches_with_different_prefixes_do_not_collide():
    """
    The reason the prefix matters: two caches on one store, told apart by their
    prefix. Ignoring it put them in the same keyspace, where each overwrote the
    other's `user:42`.
    """
    app = MemoryCacheBackend(key_prefix="app:")
    sessions = MemoryCacheBackend(key_prefix="sess:")

    await app.set("user:42", "profile")
    await sessions.set("user:42", "session")

    assert await app.get("user:42") == "profile"
    assert await sessions.get("user:42") == "session"


@pytest.mark.asyncio
async def test_delete_finds_the_prefixed_key():
    backend = MemoryCacheBackend()
    await backend.set("k", "v")
    await backend.delete("k")
    assert await backend.get("k") is None


@pytest.mark.asyncio
async def test_add_finds_the_prefixed_key():
    backend = MemoryCacheBackend()
    await backend.set("k", "v")
    assert await backend.add("k", "other") is False


@pytest.mark.asyncio
async def test_the_default_timeout_is_applied_on_set():
    backend = MemoryCacheBackend()
    await backend.set("k", "v")
    _value, expires_at = backend._store["app:1:k"]
    assert expires_at is not None, "written with no expiry"


@pytest.mark.asyncio
async def test_zero_means_never_expire_on_set():
    backend = MemoryCacheBackend()
    await backend.set("k", "v", timeout=0)
    _value, expires_at = backend._store["app:1:k"]
    assert expires_at is None


# --- versioning --------------------------------------------------------------


def test_every_backend_reads_the_version():
    for name, backend in _every_backend():
        assert backend.version == 1, f"{name} ignores CACHE_VERSION"


def test_the_version_is_part_of_the_stored_key():
    """Prefix, version, then the key."""
    assert MemoryCacheBackend()._make_key("k") == "app:1:k"


def test_raising_the_version_makes_old_entries_unreachable(monkeypatch):
    """
    The point of versioning: a deploy that changes what the cached data means
    can invalidate all of it at once, without emptying the cache and sending
    every miss to the database together.
    """
    old = MemoryCacheBackend(version=1)
    new = MemoryCacheBackend(version=2)
    new._store = old._store

    assert old._make_key("k") != new._make_key("k")


@pytest.mark.asyncio
async def test_the_previous_version_can_still_be_read():
    """A rollover you can survive: serve yesterday's value while today's fills
    in, rather than taking every miss the moment the cache goes cold."""
    cache = MemoryCacheBackend(version=1)
    await cache.set("k", "v1")

    rolled = MemoryCacheBackend(version=2)
    rolled._store = cache._store

    assert await rolled.get("k") is None
    assert await rolled.with_version(1).get("k") == "v1"


@pytest.mark.asyncio
async def test_writing_at_the_new_version_leaves_the_old_alone():
    cache = MemoryCacheBackend(version=1)
    await cache.set("k", "v1")

    rolled = MemoryCacheBackend(version=2)
    rolled._store = cache._store
    await rolled.set("k", "v2")

    assert await rolled.get("k") == "v2"
    assert await rolled.with_version(1).get("k") == "v1"


def test_with_version_shares_the_connection():
    """Shallow, so a rollover does not open a second connection to the store."""
    cache = MemoryCacheBackend()
    assert cache.with_version(2)._store is cache._store


def test_a_per_cache_version_overrides_the_setting():
    assert MemoryCacheBackend(version=7).version == 7


# --- the database backend's row locking --------------------------------------


@pytest.mark.parametrize(
    "dialect,locks",
    [
        ("postgresql", True),
        ("mysql", True),
        ("mariadb", True),
        # SQLite has no SELECT ... FOR UPDATE; it takes a write lock over the
        # whole database instead, which gives the same guarantee more bluntly.
        ("sqlite", False),
    ],
)
def test_incr_locks_the_row_where_the_database_supports_it(dialect, locks):
    """
    Without the lock, `incr` reads and writes with nothing holding the row, and
    concurrent callers lose counts -- the exact bug this replaced. It degrades
    silently, so it is worth a test: no error, just wrong numbers under load.
    """
    from buraq.contrib.cache.backends.db import _for_update

    class _Session:
        class bind:
            class dialect:
                name = dialect

    sql = _for_update("SELECT value FROM t WHERE k = :0", _Session())
    assert sql.endswith("FOR UPDATE") is locks


def test_an_unknown_dialect_does_not_claim_to_lock():
    """Better to leave it off than to send syntax the server will reject."""
    from buraq.contrib.cache.backends.db import _for_update

    class _Session:
        bind = None

    assert "FOR UPDATE" not in _for_update("SELECT 1", _Session())
