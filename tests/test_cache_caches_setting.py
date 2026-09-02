"""
The `CACHES` dict has to build the backends it names.

It did not. The loader passes `LOCATION` on to the backend as `location=`, and
no backend took that argument, so the documented configuration -- Redis with a
`LOCATION`, which is where the server address goes -- raised at the first use of
the cache:

    TypeError: RedisCacheBackend.__init__() got an unexpected keyword
               argument 'location'

`LOCATION` now means per backend what it means in Django: the server for Redis
and memcached, the directory for the file cache, the table for the database one,
and a name for the in-process one.
"""

import pytest

from buraq.conf import settings
from buraq.contrib.cache import core


@pytest.fixture(autouse=True)
def _reset_caches():
    """The loader memoises what it builds, so each test needs a clean slate."""
    core._backend = None
    core._named_backends.clear()
    yield
    core._backend = None
    core._named_backends.clear()


def _configure(monkeypatch, caches):
    monkeypatch.setattr(settings, "CACHES", caches, raising=False)
    from buraq.contrib.cache.core import caches as handler

    return handler


REDIS = "buraq.contrib.cache.backends.redis.RedisCacheBackend"
MEMORY = "buraq.contrib.cache.backends.memory.MemoryCacheBackend"
FILE = "buraq.contrib.cache.backends.file.FileCacheBackend"
DB = "buraq.contrib.cache.backends.db.DatabaseCache"
MEMCACHED = "buraq.contrib.cache.backends.memcached.MemcachedCacheBackend"


def test_the_documented_configuration_builds(monkeypatch):
    """Copied from the cache documentation, which was previously unusable."""
    caches = _configure(
        monkeypatch,
        {
            "default": {"BACKEND": REDIS, "LOCATION": "redis://localhost:6379/0"},
            "sessions": {"BACKEND": REDIS, "LOCATION": "redis://localhost:6379/1"},
            "views": {"BACKEND": MEMORY},
        },
    )

    assert caches["default"]._url == "redis://localhost:6379/0"
    assert caches["sessions"]._url == "redis://localhost:6379/1"
    assert type(caches["views"]).__name__ == "MemoryCacheBackend"


def test_two_aliases_are_two_backends(monkeypatch):
    """Otherwise a 'sessions' cache would quietly share the default's store."""
    caches = _configure(
        monkeypatch,
        {
            "default": {"BACKEND": REDIS, "LOCATION": "redis://localhost:6379/0"},
            "sessions": {"BACKEND": REDIS, "LOCATION": "redis://localhost:6379/1"},
        },
    )
    assert caches["default"] is not caches["sessions"]


def test_an_alias_is_built_once(monkeypatch):
    caches = _configure(
        monkeypatch, {"default": {"BACKEND": MEMORY}, "views": {"BACKEND": MEMORY}}
    )
    assert caches["views"] is caches["views"]


def test_an_unknown_alias_says_so(monkeypatch):
    caches = _configure(monkeypatch, {"default": {"BACKEND": MEMORY}})
    with pytest.raises(ValueError, match="No cache with alias"):
        caches["nope"]


# --- what LOCATION means, per backend ---------------------------------------


def test_location_is_the_server_for_redis(monkeypatch):
    caches = _configure(
        monkeypatch, {"default": {"BACKEND": REDIS, "LOCATION": "redis://db:6379/2"}}
    )
    assert caches["default"]._url == "redis://db:6379/2"


def test_location_is_the_directory_for_the_file_cache(monkeypatch):
    caches = _configure(
        monkeypatch, {"default": {"BACKEND": FILE, "LOCATION": "/var/tmp/cache"}}
    )
    assert "cache" in str(caches["default"]._dir)


def test_location_is_the_table_for_the_database_cache(monkeypatch):
    caches = _configure(
        monkeypatch, {"default": {"BACKEND": DB, "LOCATION": "my_cache_table"}}
    )
    assert caches["default"]._table == "my_cache_table"


def test_location_is_the_server_for_memcached(monkeypatch):
    caches = _configure(
        monkeypatch, {"default": {"BACKEND": MEMCACHED, "LOCATION": "10.0.0.5:11211"}}
    )
    assert caches["default"]._servers == [("10.0.0.5", 11211)]


def test_memcached_takes_several_servers(monkeypatch):
    caches = _configure(
        monkeypatch,
        {"default": {"BACKEND": MEMCACHED, "LOCATION": ["a:11211", "b:11212"]}},
    )
    assert caches["default"]._servers == [("a", 11211), ("b", 11212)]


def test_a_location_on_the_in_process_cache_does_not_fail(monkeypatch):
    """Django uses it to tell one local cache from another. Aliases already do
    that here, but a CACHES entry carrying one must still build."""
    caches = _configure(
        monkeypatch, {"default": {"BACKEND": MEMORY, "LOCATION": "snowflake"}}
    )
    assert type(caches["default"]).__name__ == "MemoryCacheBackend"


# --- OPTIONS and the flat settings ------------------------------------------


def test_options_reach_the_backend(monkeypatch):
    caches = _configure(
        monkeypatch, {"default": {"BACKEND": MEMORY, "OPTIONS": {"max_size": 7}}}
    )
    assert caches["default"]._max_size == 7


def test_the_flat_settings_are_used_when_there_is_no_caches_dict(monkeypatch):
    """A project that never wrote a CACHES dict keeps working."""
    monkeypatch.setattr(settings, "CACHES", {}, raising=False)
    monkeypatch.setattr(settings, "CACHE_BACKEND", MEMORY, raising=False)

    from buraq.contrib.cache.core import caches

    assert type(caches["default"]).__name__ == "MemoryCacheBackend"


def test_the_caches_dict_wins_over_the_flat_settings(monkeypatch):
    """Two ways to say the same thing, so which one is in charge has to be
    settled and stay settled."""
    monkeypatch.setattr(settings, "CACHE_BACKEND", FILE, raising=False)
    caches = _configure(monkeypatch, {"default": {"BACKEND": MEMORY}})

    assert type(caches["default"]).__name__ == "MemoryCacheBackend"


# --- TIMEOUT and KEY_PREFIX in an entry --------------------------------------


def test_a_per_entry_key_prefix_reaches_the_backend(monkeypatch):
    """
    It was read and thrown away. Two caches on one Redis, told apart by their
    prefix, both wrote unprefixed keys into the same keyspace -- so `user:42` in
    the app cache and `user:42` in the session cache were one key, each
    overwriting the other.
    """
    monkeypatch.setattr(settings, "CACHE_KEY_PREFIX", "global:", raising=False)
    caches = _configure(
        monkeypatch,
        {"default": {"BACKEND": MEMORY, "KEY_PREFIX": "sessions:"}},
    )
    assert caches["default"]._prefix == "sessions:"


def test_a_per_entry_timeout_reaches_the_backend(monkeypatch):
    monkeypatch.setattr(settings, "CACHE_DEFAULT_TIMEOUT", 300, raising=False)
    caches = _configure(
        monkeypatch, {"default": {"BACKEND": MEMORY, "TIMEOUT": 1209600}}
    )
    assert caches["default"]._default_timeout == 1209600


def test_an_entry_without_them_falls_back_to_the_settings(monkeypatch):
    monkeypatch.setattr(settings, "CACHE_KEY_PREFIX", "global:", raising=False)
    monkeypatch.setattr(settings, "CACHE_DEFAULT_TIMEOUT", 60, raising=False)
    caches = _configure(monkeypatch, {"default": {"BACKEND": MEMORY}})

    assert caches["default"]._prefix == "global:"
    assert caches["default"]._default_timeout == 60


def test_two_entries_can_differ(monkeypatch):
    caches = _configure(
        monkeypatch,
        {
            "default": {"BACKEND": MEMORY, "KEY_PREFIX": "app:", "TIMEOUT": 300},
            "sessions": {"BACKEND": MEMORY, "KEY_PREFIX": "sess:", "TIMEOUT": 1209600},
        },
    )
    assert (caches["default"]._prefix, caches["default"]._default_timeout) == (
        "app:",
        300,
    )
    assert (caches["sessions"]._prefix, caches["sessions"]._default_timeout) == (
        "sess:",
        1209600,
    )


def test_an_unknown_key_in_an_entry_is_refused(monkeypatch):
    """
    Better than dropping it. A setting that does nothing is found in production;
    one that refuses to start is found at startup. VERSION is Django's and Buraq
    has no equivalent, so it is exactly the sort of thing to say so about.
    """
    caches = _configure(monkeypatch, {"default": {"BACKEND": MEMORY, "NONSENSE": 2}})
    with pytest.raises(ValueError, match="Unknown key"):
        caches["default"]


def test_the_refusal_lists_what_is_understood(monkeypatch):
    caches = _configure(monkeypatch, {"default": {"BACKEND": MEMORY, "NOPE": 1}})
    with pytest.raises(ValueError) as caught:
        caches["default"]
    assert "OPTIONS" in str(caught.value)


# --- porting a Django CACHES dict --------------------------------------------


def test_a_django_shaped_entry_builds(monkeypatch):
    """Same keys, same meanings -- only the backend path is Buraq's."""
    caches = _configure(
        monkeypatch,
        {
            "default": {
                "BACKEND": REDIS,
                "LOCATION": "redis://127.0.0.1:6379/1",
                "TIMEOUT": 600,
                "KEY_PREFIX": "myapp",
                "OPTIONS": {},
            }
        },
    )
    backend = caches["default"]
    assert backend._url == "redis://127.0.0.1:6379/1"
    assert backend._default_timeout == 600
    assert backend._prefix == "myapp"


def test_djangos_max_entries_is_understood(monkeypatch):
    """Django spells this one in capitals; a config copied across should work
    rather than raise about a keyword argument."""
    caches = _configure(
        monkeypatch, {"default": {"BACKEND": MEMORY, "OPTIONS": {"MAX_ENTRIES": 50}}}
    )
    assert caches["default"]._max_size == 50


def test_an_option_the_backend_does_not_take_names_what_it_does(monkeypatch):
    """
    Otherwise this surfaces as a bare TypeError naming a dunder, which says
    nothing about which setting was wrong or what to write instead.
    """
    caches = _configure(
        monkeypatch, {"default": {"BACKEND": MEMORY, "OPTIONS": {"NONSENSE": 1}}}
    )
    with pytest.raises(ValueError) as caught:
        caches["default"]

    message = str(caught.value)
    assert "max_size" in message, "it should list what the backend accepts"


@pytest.mark.parametrize("key", ["KEY_FUNCTION"])
def test_django_keys_buraq_has_no_answer_for_are_refused(monkeypatch, key):
    """Loudly, at startup. Buraq builds keys from the prefix and version alone,
    so there is nothing for a key function to hook into, and accepting it would
    mean quietly ignoring it. VERSION, which Buraq does have, is supported."""
    caches = _configure(monkeypatch, {"default": {"BACKEND": MEMORY, key: "x"}})
    with pytest.raises(ValueError, match="Unknown key"):
        caches["default"]


def test_a_per_entry_version_reaches_the_backend(monkeypatch):
    """Django's VERSION, which Buraq now has: raising it makes every existing
    entry in that cache unreachable at once."""
    caches = _configure(monkeypatch, {"default": {"BACKEND": MEMORY, "VERSION": 3}})
    assert caches["default"].version == 3


def test_two_caches_can_be_on_different_versions(monkeypatch):
    caches = _configure(
        monkeypatch,
        {
            "default": {"BACKEND": MEMORY, "VERSION": 1},
            "views": {"BACKEND": MEMORY, "VERSION": 2},
        },
    )
    assert (caches["default"].version, caches["views"].version) == (1, 2)
