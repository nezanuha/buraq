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


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    monkeypatch.setattr(settings, "CACHE_DEFAULT_TIMEOUT", 300, raising=False)
    monkeypatch.setattr(settings, "CACHE_KEY_PREFIX", "app:", raising=False)


def test_every_backend_reads_the_default_timeout():
    for name, backend in _every_backend():
        assert backend._default_timeout == 300, f"{name} ignores CACHE_DEFAULT_TIMEOUT"


def test_every_backend_reads_the_key_prefix():
    for name, backend in _every_backend():
        assert backend._prefix == "app:", f"{name} ignores CACHE_KEY_PREFIX"


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
    assert list(backend._store) == ["app:k"]


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
    _value, expires_at = backend._store["app:k"]
    assert expires_at is not None, "written with no expiry"


@pytest.mark.asyncio
async def test_zero_means_never_expire_on_set():
    backend = MemoryCacheBackend()
    await backend.set("k", "v", timeout=0)
    _value, expires_at = backend._store["app:k"]
    assert expires_at is None
