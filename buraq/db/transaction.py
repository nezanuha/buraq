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

    # on_commit — runs AFTER the enclosing atomic() block commits.
    # Falls back to immediate execution when called outside any atomic block.
    async with transaction.atomic():
        await transaction.on_commit(lambda: send_welcome_email(user))
"""
import functools
import inspect
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager


@asynccontextmanager
async def _atomic_cm() -> AsyncGenerator:
    from buraq.core.db import SessionLocal, _current_session, _on_commit_callbacks
    callbacks: list = []
    tok_session = None
    tok_callbacks = None
    async with SessionLocal() as db, db.begin():
        tok_session = _current_session.set(db)
        tok_callbacks = _on_commit_callbacks.set(callbacks)
        try:
            yield db
        except Exception:
            _current_session.reset(tok_session)
            _on_commit_callbacks.reset(tok_callbacks)
            raise
    # Commit succeeded — run callbacks
    _current_session.reset(tok_session)
    _on_commit_callbacks.reset(tok_callbacks)
    for cb in callbacks:
        if inspect.iscoroutinefunction(cb):
            await cb()
        else:
            cb()


def non_atomic(func):
    """Mark a function as explicitly not requiring a transaction (no-op marker)."""
    func._non_atomic = True
    return func


async def on_commit(func):
    """
    Schedule a callback to run after the current transaction commits.

    If called inside an ``async with atomic():`` block, the callback is deferred
    until the block's commit succeeds.  If called outside any atomic block,
    the callback runs immediately (the same behaviour as Django outside a
    transaction — the "transaction" is already committed at that point).

    Must be awaited.
    """
    from buraq.core.db import _on_commit_callbacks
    callbacks = _on_commit_callbacks.get()
    if callbacks is not None:
        callbacks.append(func)
    else:
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
        from buraq.core.db import SessionLocal, _current_session, _on_commit_callbacks
        self._callbacks: list = []
        self._session_ctx = SessionLocal()
        self._db = await self._session_ctx.__aenter__()
        self._txn = self._db.begin()
        await self._txn.__aenter__()
        self._tok_session = _current_session.set(self._db)
        self._tok_callbacks = _on_commit_callbacks.set(self._callbacks)
        return self._db

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        from buraq.core.db import _current_session, _on_commit_callbacks
        _current_session.reset(self._tok_session)
        _on_commit_callbacks.reset(self._tok_callbacks)
        await self._txn.__aexit__(exc_type, exc_val, exc_tb)
        await self._session_ctx.__aexit__(exc_type, exc_val, exc_tb)
        if exc_type is None:
            for cb in self._callbacks:
                if inspect.iscoroutinefunction(cb):
                    await cb()
                else:
                    cb()


atomic = _Atomic()
