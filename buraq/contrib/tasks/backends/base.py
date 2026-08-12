"""
Abstract base class for task backends.

All backends must implement ``aenqueue()`` and ``aget_result()``.
"""
from __future__ import annotations

from typing import Any, Callable


class BaseTaskBackend:
    """
    Abstract base class for Buraq task backends.

    Subclass this to implement a custom storage/execution backend.
    All methods that interact with storage or external systems should be async.
    """

    async def aenqueue(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: dict | None = None,
        *,
        priority: int = 0,
        queue: str = "default",
    ) -> "buraq.contrib.tasks.result.TaskResult":  # noqa: F821
        raise NotImplementedError

    async def aget_result(self, task_id: str) -> "buraq.contrib.tasks.result.TaskResult | None":
        raise NotImplementedError
