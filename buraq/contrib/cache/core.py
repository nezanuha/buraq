import importlib
from typing import Any

from buraq.contrib.cache.backends.base import BaseCacheBackend

_backend: BaseCacheBackend | None = None
_named_backends: dict[str, BaseCacheBackend] = {}


def _load_backend_cls(backend_path: str, **options) -> BaseCacheBackend:
    module_path, class_name = backend_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(**options) if options else cls()


def _build_from_entry(entry: dict) -> BaseCacheBackend:
    """Build one backend from a CACHES entry.

    TIMEOUT and KEY_PREFIX used to be read and thrown away here -- only BACKEND,
    LOCATION and OPTIONS were passed on. Two caches sharing one Redis and told
    apart by KEY_PREFIX therefore wrote into the same keyspace, and a per-cache
    TIMEOUT did nothing. Both are silent, which is the worst way for a setting
    to fail.
    """
    conf = dict(entry)
    backend_path = conf.pop("BACKEND")
    opts = dict(conf.pop("OPTIONS", {}))

    for name, kwarg in (
        ("LOCATION", "location"),
        ("TIMEOUT", "timeout"),
        ("KEY_PREFIX", "key_prefix"),
        ("VERSION", "version"),
    ):
        value = conf.pop(name, None)
        if value is not None:
            opts.setdefault(kwarg, value)

    if conf:
        # Better than dropping it: a setting that does nothing is discovered in
        # production, and this is discovered at startup.
        raise ValueError(
            f"Unknown key(s) in a CACHES entry: {', '.join(sorted(conf))}. "
            f"Buraq understands BACKEND, LOCATION, TIMEOUT, KEY_PREFIX, "
            f"VERSION and OPTIONS; anything a backend takes of its own goes "
            f"in OPTIONS."
        )

    opts = {_OPTION_ALIASES.get(name, name): value for name, value in opts.items()}
    return _build(backend_path, opts)


#: Django spells some OPTIONS in capitals; a config copied across should work.
_OPTION_ALIASES = {"MAX_ENTRIES": "max_size"}


def _build(backend_path: str, opts: dict) -> BaseCacheBackend:
    """Construct the backend, and say what it accepts when it will not build.

    An OPTIONS key the backend does not take otherwise surfaces as a bare
    TypeError naming a dunder -- which says nothing about which setting was
    wrong or what to write instead.
    """
    try:
        return _load_backend_cls(backend_path, **opts)
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        import inspect

        cls = _import_backend(backend_path)
        accepted = [
            name
            for name in inspect.signature(cls.__init__).parameters
            if name not in ("self", "kwargs", "args")
        ]
        raise ValueError(
            f"A CACHES entry for {backend_path} carries an option it does not "
            f"take ({exc}). It accepts: {', '.join(accepted)}."
        ) from exc


def _import_backend(backend_path: str):
    module_path, class_name = backend_path.rsplit(".", 1)
    return getattr(importlib.import_module(module_path), class_name)


def default_entry() -> dict:
    """The CACHES entry for the default cache, whichever way it was written.

    There is one way to build a backend, and every spelling turns into an entry
    first. Two code paths is how the CACHES branch could crash on every backend
    without anyone noticing: almost nobody used it, so almost nothing tested it,
    while the flat settings everybody used stayed fine.
    """
    from buraq.conf import settings

    caches_conf = getattr(settings, "CACHES", None)
    if caches_conf and "default" in caches_conf:
        return dict(caches_conf["default"])

    url = getattr(settings, "CACHE_URL", "")
    if url:
        from buraq.contrib.cache.url import parse_cache_url

        backend_path, opts = parse_cache_url(url)
        return {"BACKEND": backend_path, "OPTIONS": opts}

    return {
        "BACKEND": getattr(
            settings,
            "CACHE_BACKEND",
            "buraq.contrib.cache.backends.memory.MemoryCacheBackend",
        )
    }


def _get_backend() -> BaseCacheBackend:
    global _backend
    if _backend is None:
        _backend = _build_from_entry(default_entry())
    return _backend


def _get_named_backend(alias: str) -> BaseCacheBackend:
    if alias not in _named_backends:
        from buraq.conf import settings
        caches_conf = getattr(settings, "CACHES", {})
        if alias not in caches_conf:
            raise ValueError(f"No cache with alias {alias!r} in CACHES setting.")
        _named_backends[alias] = _build_from_entry(caches_conf[alias])
    return _named_backends[alias]


class _CachesHandler:
    """
    Access any configured cache by alias.

    Usage::

        from buraq.contrib.cache.core import caches

        await caches["sessions"].set("key", value)
        await caches["default"].get("key")
    """

    def __getitem__(self, alias: str) -> BaseCacheBackend:
        if alias == "default":
            return _get_backend()
        return _get_named_backend(alias)


caches = _CachesHandler()


class Cache:
    """
    Unified cache interface. Automatically uses the configured backend.

    Usage:
        from buraq.contrib.cache import cache

        await cache.set("key", value, timeout=300)
        value = await cache.get("key")
        await cache.delete("key")
    """

    async def get(self, key: str) -> Any | None:
        return await _get_backend().get(key)

    async def set(self, key: str, value: Any, timeout: int | None = None) -> None:
        await _get_backend().set(key, value, timeout)

    async def delete(self, key: str) -> None:
        await _get_backend().delete(key)

    async def exists(self, key: str) -> bool:
        return await _get_backend().exists(key)

    async def clear(self) -> None:
        await _get_backend().clear()

    async def get_or_set(self, key: str, default: Any, timeout: int | None = None) -> Any:
        return await _get_backend().get_or_set(key, default, timeout)

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        return await _get_backend().get_many(keys)

    async def set_many(self, mapping: dict[str, Any], timeout: int | None = None) -> None:
        await _get_backend().set_many(mapping, timeout)

    async def delete_many(self, keys: list[str]) -> None:
        await _get_backend().delete_many(keys)

    async def add(self, key: str, value: Any, timeout: int | None = None) -> bool:
        return await _get_backend().add(key, value, timeout)

    async def incr(self, key: str, delta: int = 1) -> int:
        return await _get_backend().incr(key, delta)

    async def decr(self, key: str, delta: int = 1) -> int:
        return await _get_backend().decr(key, delta)


cache = Cache()
