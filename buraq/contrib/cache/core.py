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


def _get_backend() -> BaseCacheBackend:
    global _backend
    if _backend is None:
        from buraq.conf import settings
        caches_conf = getattr(settings, "CACHES", None)
        if caches_conf and "default" in caches_conf:
            conf = dict(caches_conf["default"])
            backend_path = conf.pop("BACKEND")
            location = conf.pop("LOCATION", None)
            opts = dict(conf.pop("OPTIONS", {}))
            if location:
                opts["location"] = location
            _backend = _load_backend_cls(backend_path, **opts)
        else:
            backend_path = getattr(
                settings,
                "CACHE_BACKEND",
                "buraq.contrib.cache.backends.memory.MemoryCacheBackend",
            )
            _backend = _load_backend_cls(backend_path)
    return _backend


def _get_named_backend(alias: str) -> BaseCacheBackend:
    if alias not in _named_backends:
        from buraq.conf import settings
        caches_conf = getattr(settings, "CACHES", {})
        if alias not in caches_conf:
            raise ValueError(f"No cache with alias {alias!r} in CACHES setting.")
        conf = dict(caches_conf[alias])
        backend_path = conf.pop("BACKEND")
        location = conf.pop("LOCATION", None)
        opts = dict(conf.pop("OPTIONS", {}))
        if location:
            opts["location"] = location
        _named_backends[alias] = _load_backend_cls(backend_path, **opts)
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
