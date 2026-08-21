"""
What each cache backend can store, and what it does with what it cannot.

The JSON backends serialized with `json.dumps(value, default=str)`, which turned
an unserializable value into its repr rather than refusing it: a datetime went
in and a string came back, and the mismatch surfaced wherever the value was next
used rather than at the call that cached it.
"""

import asyncio
import datetime
import tempfile

import pytest

from buraq.contrib.cache.backends.file import FileCacheBackend
from buraq.contrib.cache.backends.memory import MemoryCacheBackend


def _file_backend():
    return FileCacheBackend(cache_dir=tempfile.mkdtemp())


@pytest.mark.parametrize(
    "value",
    [pytest.param("hello", id="str"), pytest.param({"a": 1}, id="dict"),
     pytest.param([1, 2, 3], id="list"), pytest.param(7, id="int")],
)
def test_json_backends_round_trip_json_values(value):
    async def go():
        backend = _file_backend()
        await backend.set("k", value, 60)
        return await backend.get("k")

    assert asyncio.run(go()) == value


def test_a_value_json_cannot_hold_is_refused_not_mangled():
    """Silently storing str(value) makes the cache return a different type than
    it was given, and the caller finds out somewhere else entirely."""
    async def go():
        backend = _file_backend()
        await backend.set("created", datetime.datetime(2026, 1, 1), 60)

    with pytest.raises(TypeError, match="cannot serialize datetime"):
        asyncio.run(go())


def test_the_error_names_the_backend_and_the_key():
    async def go():
        await _file_backend().set("created", datetime.datetime(2026, 1, 1), 60)

    with pytest.raises(TypeError) as excinfo:
        asyncio.run(go())

    message = str(excinfo.value)
    assert "FileCacheBackend" in message
    assert "'created'" in message


def test_the_memory_backend_keeps_the_object_itself():
    """No serialization step, so anything goes in and the same object comes out."""
    moment = datetime.datetime(2026, 1, 1)

    async def go():
        backend = MemoryCacheBackend()
        await backend.set("created", moment, 60)
        return await backend.get("created")

    assert asyncio.run(go()) == moment
