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

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        return {k: await self.get(k) for k in keys}

    async def set_many(self, mapping: dict[str, Any], timeout: int | None = None) -> None:
        for key, value in mapping.items():
            await self.set(key, value, timeout)

    async def delete_many(self, keys: list[str]) -> None:
        for key in keys:
            await self.delete(key)
