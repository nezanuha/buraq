"""
Task — a callable decorated with @background_task.

``Task`` wraps an async or sync function and adds an ``aenqueue()`` method
that submits the function to the configured backend for background execution.
"""
from __future__ import annotations

from typing import Any, Callable

from buraq.contrib.tasks.result import TaskResult


def _get_backend():
    from buraq.conf import settings
    from buraq.utils.module_loading import import_string

    tasks_config: dict = getattr(settings, "TASKS", {})
    default_config = tasks_config.get("default", {})
    backend_path = default_config.get(
        "BACKEND",
        "buraq.contrib.tasks.backends.dummy.DummyBackend",
    )
    backend_cls = import_string(backend_path)
    return backend_cls()


class Task:
    """
    A background-task callable.

    Returned by ``@background_task``.  Call ``await task.aenqueue(...)`` to
    schedule the wrapped function for background execution.

    You can still call the wrapped function directly (synchronously or
    asynchronously) — it behaves exactly like the original function::

        await send_welcome_email(user_id=42)          # direct call
        result = await send_welcome_email.aenqueue(user_id=42)  # background
    """

    def __init__(self, func: Callable, *, queue: str = "default", priority: int = 0):
        self._func = func
        self._queue = queue
        self._priority = priority
        # Make the Task look like the wrapped function (for introspection / docs)
        self.__name__ = getattr(func, "__name__", repr(func))
        self.__module__ = getattr(func, "__module__", "")
        self.__qualname__ = getattr(func, "__qualname__", self.__name__)
        self.__doc__ = func.__doc__
        self.__wrapped__ = func

    def __call__(self, *args, **kwargs):
        return self._func(*args, **kwargs)

    async def aenqueue(self, *args, **kwargs) -> TaskResult:
        """
        Enqueue this task for background execution.

        Keyword arguments ``_queue`` and ``_priority`` are intercepted and
        forwarded to the backend; all other arguments are passed to the
        wrapped function.

        Returns a :class:`~buraq.contrib.tasks.result.TaskResult` immediately.
        The task may not have started yet — call ``await result.arefresh()``
        to poll for its current status.

        Example::

            result = await send_invoice.aenqueue(order_id=42)
            # Returns immediately with status=PENDING (DatabaseBackend)
            # or status=SUCCEEDED (DummyBackend)

            await result.arefresh()
            print(result.status)
        """
        queue = kwargs.pop("_queue", self._queue)
        priority = kwargs.pop("_priority", self._priority)
        backend = _get_backend()
        return await backend.aenqueue(
            self._func,
            args=args,
            kwargs=kwargs,
            queue=queue,
            priority=priority,
        )

    def __repr__(self) -> str:
        return f"<Task {self.__qualname__!r} queue={self._queue!r}>"
