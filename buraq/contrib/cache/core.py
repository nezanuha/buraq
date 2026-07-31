import importlib
from typing import Any

from buraq.contrib.cache.backends.base import BaseCacheBackend

_backend: BaseCacheBackend | None = None


def _get_backend() -> BaseCacheBackend:
    global _backend
    if _backend is None:
        from buraq.conf import settings
        backend_path = getattr(
            settings,
            "CACHE_BACKEND",  # type: ignore[attr-defined]
            "buraq.contrib.cache.backends.memory.MemoryCacheBackend",
        )
        module_path, class_name = backend_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        _backend = getattr(module, class_name)()
    return _backend


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


cache = Cache()
