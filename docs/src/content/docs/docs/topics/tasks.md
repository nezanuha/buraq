---
title: "Background Tasks"
description: "buraq.contrib.tasks lets you defer work to a background process so your views stay fast."
---

`buraq.contrib.tasks` lets you defer work to a background process so your views stay fast.

```python
from buraq.contrib.tasks import background_task

@background_task
async def send_welcome_email(user_id: int) -> None:
    user = await User.objects.get(id=user_id)
    await send_mail(subject="Welcome!", body="Hi", to=[user.email])
```

---

## Setup

### 1 — Configure a backend

```python
# config/settings.py
TASKS = {
    "default": {
        "BACKEND": "buraq.contrib.tasks.backends.db.DatabaseBackend",
    }
}
```

### 2 — Run `buraq migrate`

The database backend creates a `buraq_tasks` table automatically.

```bash
buraq migrate
```

### 3 — Start the worker

```bash
buraq worker
buraq worker --queue high-priority --concurrency 4
```

---

## Defining tasks

Decorate any async (or sync) function with `@background_task`:

```python
from buraq.contrib.tasks import background_task

@background_task
async def resize_image(image_id: int, width: int, height: int) -> str:
    image = await Image.objects.get(id=image_id)
    path = await do_resize(image.path, width, height)
    return path
```

The decorator returns a `Task` object that still behaves like the original function.

```python
# Direct call (runs immediately, no background)
await resize_image(image_id=1, width=800, height=600)

# Background call
result = await resize_image.aenqueue(image_id=1, width=800, height=600)
```

### Options

```python
@background_task(queue="images", priority=5)
async def resize_image(image_id: int, ...) -> str:
    ...
```

| Option | Default | Description |
|---|---|---|
| `queue` | `"default"` | Queue name — workers can listen to specific queues |
| `priority` | `0` | Lower number = higher priority within the queue |

Override per-call:

```python
result = await resize_image.aenqueue(
    image_id=1,
    width=800,
    height=600,
    _queue="urgent",
    _priority=1,
)
```

---

## Enqueuing tasks

```python
async def upload_view(request):
    image = await Image.objects.create(...)
    result = await resize_image.aenqueue(image_id=image.id, width=800, height=600)
    return JsonResponse({"task_id": result.id})
```

`aenqueue()` returns a `TaskResult` immediately.

---

## Checking task status

```python
from buraq.contrib.tasks import TaskResult, TaskStatus

result = await resize_image.aenqueue(image_id=1, width=800, height=600)

# Poll for updates
await result.arefresh()

if result.status == TaskStatus.SUCCEEDED:
    print(result.return_value)   # the return value of the task function
elif result.status == TaskStatus.FAILED:
    print(result.exception)      # the exception that was raised
```

### `TaskStatus` values

| Status | Meaning |
|---|---|
| `PENDING` | Waiting for a worker to pick it up |
| `RUNNING` | A worker is executing it now |
| `SUCCEEDED` | Completed successfully — `return_value` is set |
| `FAILED` | Raised an exception — `exception` is set |

---

## Backends

### `DummyBackend` (development / tests)

Executes tasks **immediately in-process** — no worker needed.

```python
TASKS = {
    "default": {
        "BACKEND": "buraq.contrib.tasks.backends.dummy.DummyBackend",
    }
}
```

Result status is `SUCCEEDED` (or `FAILED`) before `aenqueue()` returns.

### `DatabaseBackend` (production)

Stores tasks in the `buraq_tasks` database table. Requires `buraq worker` running separately.

```python
TASKS = {
    "default": {
        "BACKEND": "buraq.contrib.tasks.backends.db.DatabaseBackend",
    }
}
```

### Custom backend

Subclass `BaseTaskBackend` and implement two async methods:

```python
from buraq.contrib.tasks.backends.base import BaseTaskBackend
from buraq.contrib.tasks.result import TaskResult, TaskStatus

class RedisBackend(BaseTaskBackend):
    async def aenqueue(self, func, args=(), kwargs=None, *, priority=0, queue="default") -> TaskResult:
        ...

    async def aget_result(self, task_id: str) -> TaskResult | None:
        ...
```

---

## Testing

Use `DummyBackend` in tests so tasks execute immediately:

```python
from buraq.test import TestCase, override_settings

DUMMY_TASKS = {"default": {"BACKEND": "buraq.contrib.tasks.backends.dummy.DummyBackend"}}

@override_settings(TASKS=DUMMY_TASKS)
class EmailTaskTests(TestCase):
    async def test_welcome_email_sent(self):
        result = await send_welcome_email.aenqueue(user_id=self.user.id)
        self.assertEqual(result.status.value, "SUCCEEDED")
```

---

## API reference

### `@background_task`

| Parameter | Default | Description |
|---|---|---|
| `queue` | `"default"` | Default queue name |
| `priority` | `0` | Default priority |

### `Task`

| Method | Description |
|---|---|
| `await task.aenqueue(*args, **kwargs)` | Enqueue for background execution; returns `TaskResult` |
| `await task(*args, **kwargs)` | Call directly (immediate, synchronous) |

### `TaskResult`

| Attribute | Description |
|---|---|
| `id` | Unique task ID |
| `status` | `TaskStatus` enum value |
| `return_value` | Return value (set when `SUCCEEDED`) |
| `exception` | Exception instance (set when `FAILED`) |
| `attempts` | Number of execution attempts |
| `await result.arefresh()` | Refresh status from backend |

### `BaseTaskBackend`

| Method | Description |
|---|---|
| `await backend.aenqueue(func, args, kwargs, *, priority, queue)` | Enqueue the function |
| `await backend.aget_result(task_id)` | Fetch the current `TaskResult` |
