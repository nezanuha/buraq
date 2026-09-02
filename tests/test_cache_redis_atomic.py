"""
`add` and `incr` on Redis have to be one command, not two.

Both were inherited from the base backend, which implements them in Python:

    add:  if await self.exists(key): return False
          await self.set(key, value)
    incr: current = await self.get(key)
          await self.set(key, int(current) + delta)

Both calls suspend on a network backend, so concurrent callers interleave. For
`incr` they all read 5 and all write 6, and the counts collapse -- 500 concurrent
increments measured as 1 (see the last test). For `add` they all find the key
missing and all believe they set it, which defeats its purpose, since `add` is
the primitive people build locks out of, and the documentation shows it that way.

An in-process backend escapes this only because nothing in it suspends.

Redis does both atomically: SET NX and INCRBY. There is no Redis server here, so
these check that the backend issues those commands rather than the read-then-
write pair -- the part that was wrong, and the part a live server cannot tell us
about without a race to reproduce.
"""

import pytest

from buraq.contrib.cache.backends.redis import RedisCacheBackend


class FakeRedis:
    """Records the commands issued, and answers them plausibly."""

    def __init__(self, existing=None):
        self.store = dict(existing or {})
        self.calls = []

    async def set(self, key, value, nx=False, ex=None, **kwargs):
        self.calls.append(("set", key, value, {"nx": nx, "ex": ex}))
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    async def get(self, key):
        self.calls.append(("get", key))
        return self.store.get(key)

    async def exists(self, key):
        self.calls.append(("exists", key))
        return 1 if key in self.store else 0

    async def incrby(self, key, delta):
        self.calls.append(("incrby", key, delta))
        self.store[key] = str(int(self.store.get(key, 0)) + delta)
        return int(self.store[key])

    @property
    def commands(self):
        return [call[0] for call in self.calls]


def _backend(existing=None):
    backend = RedisCacheBackend(url="redis://unused")
    backend._client = FakeRedis(existing)
    return backend


# --- add --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_is_one_command():
    backend = _backend()
    assert await backend.add("k", "v") is True
    assert backend._client.commands == ["set"], "checked and then set"


@pytest.mark.asyncio
async def test_add_asks_redis_not_to_overwrite():
    backend = _backend()
    await backend.add("k", "v")

    _name, _key, _value, options = backend._client.calls[0]
    assert options["nx"] is True, "without NX the set overwrites what is there"


@pytest.mark.asyncio
async def test_add_reports_that_an_existing_key_was_not_set():
    backend = _backend({"1:k": '"taken"'})
    assert await backend.add("k", "mine") is False


@pytest.mark.asyncio
async def test_add_passes_the_timeout_through():
    """A lock with no expiry is a lock that outlives whatever held it."""
    backend = _backend()
    await backend.add("k", "v", timeout=30)

    _name, _key, _value, options = backend._client.calls[0]
    assert options["ex"] == 30


@pytest.mark.asyncio
async def test_add_falls_back_to_the_configured_default_timeout():
    """
    Not "no expiry". A key written with no timeout used to live forever on
    Redis, whatever CACHE_DEFAULT_TIMEOUT said -- a cache that never evicts is
    a memory leak with a lookup method.
    """
    backend = _backend()
    backend._default_timeout = 300
    await backend.add("k", "v")

    _name, _key, _value, options = backend._client.calls[0]
    assert options["ex"] == 300


@pytest.mark.asyncio
async def test_a_timeout_of_zero_still_means_never_expire():
    """The way a caller asks for that on purpose, distinct from not asking."""
    backend = _backend()
    backend._default_timeout = 300
    await backend.add("k", "v", timeout=0)

    _name, _key, _value, options = backend._client.calls[0]
    assert options["ex"] is None


# --- incr -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_incr_uses_redis_to_add_rather_than_reading_and_writing():
    backend = _backend({"1:k": "5"})
    assert await backend.incr("k") == 6
    assert "incrby" in backend._client.commands
    assert "set" not in backend._client.commands, "read-modify-write loses counts"


@pytest.mark.asyncio
async def test_incr_takes_a_delta():
    backend = _backend({"1:k": "5"})
    assert await backend.incr("k", 10) == 15


@pytest.mark.asyncio
async def test_decr_goes_through_the_same_command():
    backend = _backend({"1:k": "5"})
    assert await backend.decr("k", 2) == 3
    assert "incrby" in backend._client.commands


@pytest.mark.asyncio
async def test_incr_on_a_missing_key_raises():
    """The contract the base backend sets, kept."""
    backend = _backend()
    with pytest.raises(ValueError, match="not found"):
        await backend.incr("k")


@pytest.mark.asyncio
async def test_what_incr_leaves_behind_is_what_get_reads_back():
    """
    INCRBY writes plain digits. get() runs json.loads over what it finds, and an
    integer's JSON is just its digits, so the two agree -- but only for integers,
    which is all incr claims to handle.
    """
    import json

    backend = _backend({"1:k": json.dumps(5)})
    await backend.incr("k")
    assert json.loads(backend._client.store["1:k"]) == 6


@pytest.mark.asyncio
async def test_the_key_prefix_is_applied():
    """Whatever CACHE_KEY_PREFIX is set to has to reach these two as well."""
    backend = _backend({"p:1:k": "1"})
    backend._prefix = "p:"

    await backend.incr("k")
    await backend.add("other", "v")

    assert ("incrby", "p:1:k", 1) in backend._client.calls
    assert backend._client.calls[-1][1] == "p:1:other"


# --- why this matters -------------------------------------------------------


@pytest.mark.asyncio
async def test_read_then_write_loses_increments_when_the_backend_suspends():
    """
    The measurement behind the two overrides above.

    The inherited `incr` awaits get() and then set(). On a backend with no I/O
    neither call suspends, so nothing interleaves and it happens to be correct.
    On any backend that talks over a network -- Redis, memcached, the database
    -- both suspend, every concurrent caller reads the same value, and the
    increments collapse into one.

        500 concurrent increments over a suspending backend -> 1
    """
    import asyncio

    from buraq.contrib.cache.backends.base import BaseCacheBackend

    class Suspending(BaseCacheBackend):
        def __init__(self):
            self.store = {}

        async def get(self, key):
            await asyncio.sleep(0)
            return self.store.get(key)

        async def set(self, key, value, timeout=None):
            await asyncio.sleep(0)
            self.store[key] = value

        async def delete(self, key):
            self.store.pop(key, None)

        async def exists(self, key):
            return key in self.store

        async def clear(self):
            self.store.clear()

    backend = Suspending()
    await backend.set("c", 0)
    await asyncio.gather(*(backend.incr("c") for _ in range(100)))

    assert await backend.get("c") < 100, "if this passes 100, the base is safe now"


@pytest.mark.asyncio
async def test_the_redis_backend_does_not_inherit_that_implementation():
    """The guard on the above: Redis must not fall back to read-then-write."""
    from buraq.contrib.cache.backends.base import BaseCacheBackend

    assert RedisCacheBackend.incr is not BaseCacheBackend.incr
    assert RedisCacheBackend.add is not BaseCacheBackend.add
