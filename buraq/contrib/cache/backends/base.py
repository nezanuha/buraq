import asyncio
from abc import ABC, abstractmethod
from typing import Any


class BaseCacheBackend(ABC):
    @abstractmethod
    async def get(self, key: str) -> Any | None: ...

    @abstractmethod
    async def set(self, key: str, value: Any, timeout: int | None = None) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def exists(self, key: str) -> bool: ...

    @abstractmethod
    async def clear(self) -> None: ...

    async def get_or_set(self, key: str, default: Any, timeout: int | None = None) -> Any:
        value = await self.get(key)
        if value is None:
            value = default() if callable(default) else default
            await self.set(key, value, timeout)
        return value

    async def add(self, key: str, value: Any, timeout: int | None = None) -> bool:
        """Set key only if not already present. Returns True if the key was set."""
        if await self.exists(key):
            return False
        await self.set(key, value, timeout)
        return True

    async def incr(self, key: str, delta: int = 1) -> int:
        """Increment the integer value stored at key. Raises ValueError if key missing."""
        current = await self.get(key)
        if current is None:
            raise ValueError(f"Cache key {key!r} not found.")
        new_value = int(current) + delta
        await self.set(key, new_value)
        return new_value

    async def decr(self, key: str, delta: int = 1) -> int:
        """Decrement the integer value stored at key."""
        return await self.incr(key, -delta)

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        return {k: await self.get(k) for k in keys}

    async def set_many(self, mapping: dict[str, Any], timeout: int | None = None) -> None:
        for key, value in mapping.items():
            await self.set(key, value, timeout)

    async def delete_many(self, keys: list[str]) -> None:
        for key in keys:
            await self.delete(key)

    # ── Sync wrappers ──────────────────────────────────────────────────────────

    def _run_async(self, coro):
        try:
            return asyncio.run(coro)
        except RuntimeError:
            return asyncio.get_event_loop().run_until_complete(coro)

    def get_sync(self, key: str) -> Any | None:
        return self._run_async(self.get(key))

    def set_sync(self, key: str, value: Any, timeout: int | None = None) -> None:
        self._run_async(self.set(key, value, timeout))

    def delete_sync(self, key: str) -> None:
        self._run_async(self.delete(key))

    def delete_many_sync(self, keys: list[str]) -> None:
        self._run_async(self.delete_many(keys))

    def clear_sync(self) -> None:
        self._run_async(self.clear())
