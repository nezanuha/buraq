"""
Database transaction helpers — atomic(), on_commit(), and savepoint utilities.

Usage:
    from buraq.db import transaction

    # Context manager
    async with transaction.atomic():
        await Post.objects.create(title="Hello")
        await Tag.objects.create(name="python")

    # Decorator
    @transaction.atomic
    async def create_post_with_tags(title, tags):
        post = await Post.objects.create(title=title)
        for tag in tags:
            await post.tags.add(tag)
        return post
"""
import functools
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager


# Internal generator — named separately so _Atomic can reference it without
# recursive self-reference after `atomic = _Atomic()` rebinds the name.
@asynccontextmanager
async def _atomic_cm() -> AsyncGenerator:
    from buraq.core.db import SessionLocal
    async with SessionLocal() as db, db.begin():
        yield db


def non_atomic(func):
    """Mark a function as explicitly not requiring a transaction (no-op marker)."""
    func._non_atomic = True
    return func


async def on_commit(func):
    """
    Run a callback after the current transaction commits.
    In Buraq this runs immediately (no transaction stack tracking).
    Must be awaited inside an async context.
    """
    import inspect
    if inspect.iscoroutinefunction(func):
        await func()
    else:
        func()


class TransactionManagementError(Exception):
    pass


class _Atomic:
    """
    Dual-use: async context manager AND decorator.

        async with atomic():
            ...

        @atomic
        async def my_view():
            ...
    """

    def __call__(self, func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            async with _atomic_cm():
                return await func(*args, **kwargs)
        return wrapper

    async def __aenter__(self):
        from buraq.core.db import SessionLocal
        self._session = SessionLocal()
        self._db = await self._session.__aenter__()
        self._txn = self._db.begin()
        await self._txn.__aenter__()
        return self._db

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._txn.__aexit__(exc_type, exc_val, exc_tb)
        await self._session.__aexit__(exc_type, exc_val, exc_tb)


atomic = _Atomic()
