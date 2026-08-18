---
title: "Sync and Async Code"
description: "Buraq is async-first: the ORM is natively async, sync views run in a worker thread, and blocking libraries go through asyncio.to_thread()."
---

Buraq is async-first. The ORM, views, forms, and signals are all natively
asynchronous — there is no synchronous implementation underneath being wrapped.

This page explains what that means in practice: when you can write ordinary
synchronous code, when you can't, and how to call blocking libraries without
stalling the event loop.

## How Buraq differs from Django

Django is **sync-first with async adapters**. Its ORM is synchronous, and the
async methods added in 4.1 (`aget()`, `acreate()`, `afilter()`) wrap the sync
implementation:

```python
# django/db/models/query.py
async def aget(self, *args, **kwargs):
    return await sync_to_async(self.get)(*args, **kwargs)
```

`sync_to_async` defaults to `thread_sensitive=True`, which runs every call on a
**single shared thread** so thread-local database connections stay valid. The
practical effect is that concurrent async queries queue behind one another —
eight 100 ms queries take roughly 0.8 s rather than 0.1 s. You get async syntax
without async concurrency.

Buraq is the mirror image — **async-first, with no sync layer**:

| | Django | Buraq |
|---|---|---|
| Core | synchronous | asynchronous |
| ORM | sync, with async wrappers | async only |
| Async queries | serialised on one shared thread | true async I/O |
| Sync bridge | `sync_to_async` / `async_to_sync` | not needed — see below |

Because queries are genuinely non-blocking, a single worker handles thousands of
concurrent database calls without a thread each.

## Writing views

Views should be `async def`:

```python
async def post_list(request):
    posts = await Post.objects.filter(published=True)
    return await render(request, "posts/list.html", {"posts": posts})
```

A plain `def` view also works — Buraq runs it in a worker thread so it cannot
block the event loop:

```python
def health_check(request):
    return {"status": "ok"}      # fine: no database access
```

:::caution[The ORM is not reachable from a sync view]
A synchronous view runs in a worker thread where no event loop is running, so
there is nothing to `await` on. Every query in Buraq must be awaited:

```python
def broken_view(request):
    posts = Post.objects.all()   # builds a QuerySet, never executes it
    return list(posts)           # TypeError: 'QuerySet' object is not iterable
```

Use a sync view only for work that never touches the database — health checks,
pure computation, rendering from data you already have. Anything else should be
`async def`.
:::

## Calling blocking libraries

The common real-world case is not "I want sync" but *"I have a synchronous
library and don't want to block the loop."* Image processing, data frames, and
vendor SDKs are usually synchronous.

Wrap those calls in `asyncio.to_thread()`:

```python
import asyncio
from PIL import Image


async def create_thumbnail(request, pk: int):
    photo = await get_object_or_404(Photo, id=pk)

    def resize():
        img = Image.open(photo.path)          # blocking
        img.thumbnail((320, 320))
        img.save(photo.thumb_path)

    await asyncio.to_thread(resize)
    return await render(request, "photos/done.html", {"photo": photo})
```

Without the wrapper, the resize would freeze **every** concurrent request for its
duration, not just this one.

The same applies to any synchronous network client:

```python
# Blocks the whole event loop
data = requests.get(url).json()

# Correct: run it off the loop
data = await asyncio.to_thread(lambda: requests.get(url).json())

# Better still: use an async client
async with httpx.AsyncClient() as client:
    data = (await client.get(url)).json()
```

## Extension points accept both

Anywhere Buraq calls code *you* supply, it detects whether the callable is
asynchronous and does the right thing — async ones are awaited, synchronous ones
are run in a thread so they don't block the loop. No decorator required.

This applies to signal receivers, form field validators, `on_commit()` callbacks,
background tasks, sitemap `items()`, and template context processors:

```python
from buraq.signals import post_save


@post_save.connect
async def notify_async(sender, instance, created, **kwargs):
    await send_webhook(instance.id)          # awaited


@post_save.connect
def notify_sync(sender, instance, created, **kwargs):
    send_webhook_blocking(instance.id)       # run via asyncio.to_thread()
```

Both are correct. Write whichever suits the code you have.

## Why there is no `sync_to_async`

Django ships `sync_to_async` and `async_to_sync` because its core is
synchronous and it needs bridges in both directions. Buraq needs neither:

- **Calling sync code from async** — use `asyncio.to_thread()` from the standard
  library. Django's `sync_to_async` mainly adds `thread_sensitive=True` to
  preserve thread-local database connections; Buraq's ORM is async and holds no
  thread-locals, so there is nothing to preserve.
- **Calling async code from sync** — use `asyncio.run()`. This is how management
  commands work, and it is appropriate in scripts and one-off tooling.

Adding a dependency to re-export what the standard library already provides
would only suggest Buraq has a synchronous mode. It does not.

:::note
Do not call `asyncio.run()` inside a request. A running event loop cannot be
nested, and creating a new one per call fragments the connection pool —
connections are bound to the loop that created them. Inside a view, `await`.
:::

## Management commands

Command handlers are asynchronous and executed with `asyncio.run()` by the
command runner, so you can await the ORM directly:

```python
from buraq.management.base import BaseCommand


class Command(BaseCommand):
    help = "Deactivate stale accounts"

    async def handle(self, *args, **options):
        stale = await User.objects.filter(last_login__lt=cutoff)
        for user in stale:
            user.is_active = False
            await user.save()
        self.stdout.write(f"Deactivated {len(stale)} account(s).")
```

## Summary

- Write `async def` views and `await` every query.
- Sync views are permitted but cannot reach the database.
- Wrap blocking libraries in `await asyncio.to_thread(...)`.
- Signal receivers, validators, and callbacks may be either — Buraq adapts.
- Use `asyncio.run()` only outside the request cycle.
