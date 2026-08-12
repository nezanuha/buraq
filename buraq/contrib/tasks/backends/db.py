"""
Database-backed task backend.

Persists tasks to the ``buraq_tasks`` table.  A separate worker process
(``buraq worker``) polls the table, executes pending tasks, and updates their
status.

Configuration::

    TASKS = {
        "default": {
            "BACKEND": "buraq.contrib.tasks.backends.db.DatabaseBackend",
        }
    }

Run the worker::

    buraq worker
    buraq worker --queue high-priority --concurrency 4

Task rows are stored with:

- ``id``          — UUID primary key
- ``queue``       — queue name (default: "default")
- ``func_path``   — dotted import path to the task function
- ``args_json``   — JSON-encoded positional args
- ``kwargs_json`` — JSON-encoded keyword args
- ``status``      — PENDING / RUNNING / SUCCEEDED / FAILED
- ``return_json`` — JSON-encoded return value (on success)
- ``error``       — exception repr (on failure)
- ``attempts``    — how many times execution was attempted
- ``priority``    — lower number = higher priority
- ``created_at``  — UTC timestamp
- ``started_at``  — UTC timestamp (nullable)
- ``finished_at`` — UTC timestamp (nullable)
"""
from __future__ import annotations

import importlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any, Callable

import sqlalchemy as sa

from buraq.contrib.tasks.backends.base import BaseTaskBackend
from buraq.contrib.tasks.result import TaskResult, TaskStatus
from buraq.core.db import Base

# ── SQLAlchemy table definition ───────────────────────────────────────────────

buraq_task_table = sa.Table(
    "buraq_tasks",
    Base.metadata,
    sa.Column("id", sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
    sa.Column("queue", sa.String(128), nullable=False, default="default", index=True),
    sa.Column("func_path", sa.String(512), nullable=False),
    sa.Column("args_json", sa.Text, nullable=False, default="[]"),
    sa.Column("kwargs_json", sa.Text, nullable=False, default="{}"),
    sa.Column("status", sa.String(16), nullable=False, default=TaskStatus.PENDING.value, index=True),
    sa.Column("return_json", sa.Text, nullable=True),
    sa.Column("error", sa.Text, nullable=True),
    sa.Column("attempts", sa.Integer, nullable=False, default=0),
    sa.Column("priority", sa.Integer, nullable=False, default=0),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
)


def _func_path(func: Callable) -> str:
    return f"{func.__module__}.{func.__qualname__}"


def _import_func(path: str) -> Callable:
    module_path, func_name = path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


class DatabaseBackend(BaseTaskBackend):
    """
    Persists tasks to the database and executes them via a worker process.

    ``aenqueue()`` inserts a row and returns a ``TaskResult`` with status
    ``PENDING``.  Actual execution happens when the worker polls the queue.
    """

    async def aenqueue(
        self,
        func: Callable,
        args: tuple = (),
        kwargs: dict | None = None,
        *,
        priority: int = 0,
        queue: str = "default",
    ) -> TaskResult:
        from buraq.core.db import SessionLocal

        kwargs = kwargs or {}
        task_id = str(uuid.uuid4())
        async with SessionLocal() as db:
            await db.execute(
                buraq_task_table.insert().values(
                    id=task_id,
                    queue=queue,
                    func_path=_func_path(func),
                    args_json=json.dumps(list(args)),
                    kwargs_json=json.dumps(kwargs),
                    status=TaskStatus.PENDING.value,
                    priority=priority,
                    created_at=datetime.now(UTC),
                )
            )
            await db.commit()

        return TaskResult(id=task_id, status=TaskStatus.PENDING, backend=self)

    async def aget_result(self, task_id: str) -> TaskResult | None:
        from buraq.core.db import SessionLocal

        async with SessionLocal() as db:
            row = await db.execute(
                sa.select(buraq_task_table).where(buraq_task_table.c.id == task_id)
            )
            row = row.fetchone()

        if row is None:
            return None

        exc = None
        if row.status == TaskStatus.FAILED.value and row.error:
            exc = RuntimeError(row.error)

        return_value = None
        if row.status == TaskStatus.SUCCEEDED.value and row.return_json:
            try:
                return_value = json.loads(row.return_json)
            except Exception:
                return_value = row.return_json

        return TaskResult(
            id=row.id,
            status=TaskStatus(row.status),
            return_value=return_value,
            exception=exc,
            attempts=row.attempts,
            backend=self,
        )
