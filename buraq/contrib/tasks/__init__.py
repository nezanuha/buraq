"""
buraq.contrib.tasks — Background task system.

Quick start::

    # 1. Add TASKS to settings
    TASKS = {
        "default": {
            "BACKEND": "buraq.contrib.tasks.backends.db.DatabaseBackend",
        }
    }

    # 2. Decorate a function
    from buraq.contrib.tasks import background_task

    @background_task
    async def send_welcome_email(user_id: int) -> None:
        user = await User.objects.get(id=user_id)
        await send_mail(
            subject="Welcome!",
            body=f"Hi {user.username}",
            to=[user.email],
        )

    # 3. Enqueue it from a view
    async def register(request):
        user = await User.objects.create(...)
        await send_welcome_email.aenqueue(user_id=user.id)
        return redirect("/")

    # 4. Run the worker (separate process)
    #    buraq worker

The decorated function still works as a regular async function — call it
directly for synchronous/immediate execution, or use ``.aenqueue()`` to
defer execution to a worker process.

Backends
--------
- ``DummyBackend``   — Executes immediately in-process (tests / development).
- ``DatabaseBackend`` — Stores tasks in the DB; a worker polls and executes them.

Custom backends can be created by subclassing
``buraq.contrib.tasks.backends.base.BaseTaskBackend``.
"""
from __future__ import annotations

from collections.abc import Callable

from buraq.contrib.tasks.backends.base import BaseTaskBackend
from buraq.contrib.tasks.result import TaskResult, TaskStatus
from buraq.contrib.tasks.task import Task


def background_task(
    func: Callable | None = None,
    *,
    queue: str = "default",
    priority: int = 0,
) -> Task | Callable[[Callable], Task]:
    """
    Decorator that marks a function as a background task.

    Usage — bare decorator::

        @background_task
        async def send_email(to: str, subject: str) -> None:
            ...

    Usage — with options::

        @background_task(queue="high-priority", priority=10)
        async def process_payment(order_id: int) -> None:
            ...

    Enqueue for background execution::

        result = await send_email.aenqueue(to="a@b.com", subject="Hi")

    Or call directly (immediate, no background)::

        await send_email(to="a@b.com", subject="Hi")
    """
    if func is not None:
        # Called as @background_task (no parentheses)
        return Task(func, queue=queue, priority=priority)

    # Called as @background_task(...) — return the real decorator
    def decorator(fn: Callable) -> Task:
        return Task(fn, queue=queue, priority=priority)

    return decorator


__all__ = [
    "background_task",
    "Task",
    "TaskResult",
    "TaskStatus",
    "BaseTaskBackend",
]
