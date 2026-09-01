"""
One `CACHE_URL`, the way there is one `DATABASE_URL`.

Configuring a cache took a backend path plus whichever of six settings that
backend happened to read -- CACHE_REDIS_URL, CACHE_MEMCACHED_URL,
CACHE_MEMCACHED_SERVERS, CACHE_FILE_PATH, CACHE_TABLE. Most are meaningless for
any given backend, and nothing in a settings file said which were live, so the
same address could be written twice with only one of them read.
"""

import pytest

from buraq.conf import settings
from buraq.contrib.cache import core
from buraq.contrib.cache.url import parse_cache_url
from buraq.exceptions import ImproperlyConfigured


@pytest.fixture(autouse=True)
def _reset():
    core._backend = None
    core._named_backends.clear()
    yield
    core._backend = None
    core._named_backends.clear()


def _name(backend_path):
    return backend_path.rsplit(".", 1)[1]


# --- parsing ----------------------------------------------------------------


@pytest.mark.parametrize(
    "url,backend",
    [
        ("redis://localhost:6379/0", "RedisCacheBackend"),
        ("rediss://user:pw@host:6380/1", "RedisCacheBackend"),
        ("memcached://localhost:11211", "MemcachedCacheBackend"),
        ("memcache://localhost:11211", "MemcachedCacheBackend"),
        ("file:///var/tmp/cache", "FileCacheBackend"),
        ("db://my_table", "DatabaseCache"),
        ("database://my_table", "DatabaseCache"),
        ("locmem://", "MemoryCacheBackend"),
        ("memory://", "MemoryCacheBackend"),
    ],
)
def test_the_scheme_picks_the_backend(url, backend):
    assert _name(parse_cache_url(url)[0]) == backend


def test_a_redis_url_is_passed_on_whole():
    """The client understands passwords, TLS and database numbers; taking it
    apart here would only lose some of them."""
    _backend, options = parse_cache_url("rediss://user:pw@host:6380/2")
    assert options["url"] == "rediss://user:pw@host:6380/2"


def test_a_file_url_gives_the_directory():
    _backend, options = parse_cache_url("file:///var/tmp/cache")
    assert options["cache_dir"] == "/var/tmp/cache"


def test_a_relative_file_url_works():
    _backend, options = parse_cache_url("file://./cache")
    assert "cache" in options["cache_dir"]


def test_a_database_url_gives_the_table():
    """The connection is DATABASE_URL's business; only the table is left."""
    _backend, options = parse_cache_url("db://my_cache_table")
    assert options["table"] == "my_cache_table"


def test_a_memcached_url_gives_one_server():
    _backend, options = parse_cache_url("memcached://localhost:11211")
    assert options["location"] == ["localhost:11211"]


def test_a_memcached_url_takes_several_servers():
    _backend, options = parse_cache_url("memcached://a:11211,b:11211")
    assert options["location"] == ["a:11211", "b:11211"]


# --- what it refuses ---------------------------------------------------------


@pytest.mark.parametrize("bad", ["", "   ", None, 5])
def test_an_empty_url_is_refused(bad):
    with pytest.raises(ImproperlyConfigured, match="CACHE_URL"):
        parse_cache_url(bad)


def test_a_url_with_no_scheme_says_the_scheme_is_what_matters():
    with pytest.raises(ImproperlyConfigured, match="no scheme"):
        parse_cache_url("localhost")


def test_a_host_and_port_alone_still_names_the_schemes():
    """`urlparse` reads "localhost:6379" as the scheme "localhost", so this
    lands on the unknown-scheme path -- which has to be just as useful."""
    with pytest.raises(ImproperlyConfigured) as caught:
        parse_cache_url("localhost:6379")
    assert "redis" in str(caught.value)


def test_an_unknown_scheme_lists_the_known_ones():
    with pytest.raises(ImproperlyConfigured) as caught:
        parse_cache_url("mongodb://localhost:27017")
    message = str(caught.value)
    assert "redis" in message and "memcached" in message


def test_a_file_url_with_no_directory_is_refused():
    with pytest.raises(ImproperlyConfigured, match="names no directory"):
        parse_cache_url("file://")


# --- the setting -------------------------------------------------------------


def test_cache_url_builds_the_backend(monkeypatch):
    monkeypatch.setattr(settings, "CACHES", {}, raising=False)
    monkeypatch.setattr(settings, "CACHE_URL", "redis://localhost:6379/3", raising=False)

    from buraq.contrib.cache.core import caches

    assert caches["default"]._url == "redis://localhost:6379/3"


def test_caches_wins_over_cache_url(monkeypatch):
    """The most specific way of saying it stays in charge."""
    monkeypatch.setattr(settings, "CACHE_URL", "redis://localhost:6379/3", raising=False)
    monkeypatch.setattr(
        settings,
        "CACHES",
        {"default": {"BACKEND": "buraq.contrib.cache.backends.memory.MemoryCacheBackend"}},
        raising=False,
    )

    from buraq.contrib.cache.core import caches

    assert type(caches["default"]).__name__ == "MemoryCacheBackend"


def test_cache_url_wins_over_cache_backend(monkeypatch):
    monkeypatch.setattr(settings, "CACHES", {}, raising=False)
    monkeypatch.setattr(
        settings,
        "CACHE_BACKEND",
        "buraq.contrib.cache.backends.file.FileCacheBackend",
        raising=False,
    )
    monkeypatch.setattr(settings, "CACHE_URL", "locmem://", raising=False)

    from buraq.contrib.cache.core import caches

    assert type(caches["default"]).__name__ == "MemoryCacheBackend"


def test_the_old_settings_still_work(monkeypatch):
    """A project that never writes a CACHE_URL keeps working unchanged."""
    monkeypatch.setattr(settings, "CACHES", {}, raising=False)
    monkeypatch.setattr(settings, "CACHE_URL", "", raising=False)
    monkeypatch.setattr(
        settings,
        "CACHE_BACKEND",
        "buraq.contrib.cache.backends.memory.MemoryCacheBackend",
        raising=False,
    )

    from buraq.contrib.cache.core import caches

    assert type(caches["default"]).__name__ == "MemoryCacheBackend"


def test_the_default_is_empty():
    """So nothing changes for a project that has not adopted it."""
    from buraq.conf.defaults import BuraqSettings

    assert BuraqSettings.model_fields["CACHE_URL"].default == ""
