"""
Dummy (immediate) task backend — executes tasks synchronously in-process.

Useful for tests and development.  The task runs immediately inside
``aenqueue()`` before it returns; no real background execution occurs.

Configuration::

    TASKS = {
        "default": {
            "BACKEND": "buraq.contrib.tasks.backends.dummy.DummyBackend",
        }
    }
"""
from __future__ import annotations

import asyncio
import inspect
import uuid
from typing import Any, Callable

from buraq.contrib.tasks.backends.base import BaseTaskBackend
from buraq.contrib.tasks.result import TaskResult, TaskStatus


class DummyBackend(BaseTaskBackend):
    """
    Executes tasks immediately and in-process.

    Results are stored in memory — they do not persist across restarts.

    Usage in tests::

        with override_settings(TASKS={"default": {"BACKEND": "buraq.contrib.tasks.backends.dummy.DummyBackend"}}):
            result = await my_task.aenqueue(user_id=1)
            assert result.status == TaskStatus.SUCCEEDED
    """

    def __init__(self):
        self._results: dict[str, TaskResult] = {}

    async def aenqueue(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: dict | None = None,
        *,
        priority: int = 0,
        queue: str = "default",
    ) -> TaskResult:
        kwargs = kwargs or {}
        task_id = str(uuid.uuid4())
        result = TaskResult(id=task_id, status=TaskStatus.RUNNING, backend=self, attempts=1)

        try:
            if inspect.iscoroutinefunction(func):
                return_value = await func(*args, **kwargs)
            else:
                return_value = await asyncio.to_thread(func, *args, **kwargs)
            result.status = TaskStatus.SUCCEEDED
            result.return_value = return_value
        except Exception as exc:
            result.status = TaskStatus.FAILED
            result.exception = exc

        self._results[task_id] = result
        return result

    async def aget_result(self, task_id: str) -> TaskResult | None:
        return self._results.get(task_id)

    def clear(self) -> None:
        """Remove all stored results."""
        self._results.clear()
