"""
TaskResult — the return value of Task.aenqueue().

Holds the current state of a background task and lets callers refresh or wait
for the result.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class TaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@dataclass
class TaskResult:
    """
    The result of an enqueued background task.

    Attributes:
        id:         Unique identifier for the enqueued task.
        status:     Current ``TaskStatus`` — PENDING, RUNNING, SUCCEEDED, FAILED.
        return_value: The value returned by the task function (only set when SUCCEEDED).
        exception:  The exception raised by the task (only set when FAILED).
        backend:    The backend instance that created this result.
        attempts:   How many times the task has been attempted.
    """

    id: str
    status: TaskStatus = TaskStatus.PENDING
    return_value: Any = None
    exception: BaseException | None = None
    backend: Any = None
    attempts: int = 0

    async def arefresh(self) -> "TaskResult":
        """Fetch the latest status from the backend and update this result in-place."""
        if self.backend is not None:
            updated = await self.backend.aget_result(self.id)
            if updated is not None:
                self.status = updated.status
                self.return_value = updated.return_value
                self.exception = updated.exception
                self.attempts = updated.attempts
        return self

    def __repr__(self) -> str:
        return f"<TaskResult id={self.id!r} status={self.status.value}>"
