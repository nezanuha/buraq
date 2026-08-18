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
    # Pass an async def or a plain callable. Do NOT wrap an async function in
    # a lambda — the lambda returns a coroutine object, not a coroutine function,
    # which will be awaited correctly by on_commit's runner.
    async with transaction.atomic():
        await transaction.on_commit(send_welcome_email)   # async def — correct
        # await transaction.on_commit(lambda: send_welcome_email(user))  ← works too
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
    try:
        async with SessionLocal() as db, db.begin():
            tok_session = _current_session.set(db)
            tok_callbacks = _on_commit_callbacks.set(callbacks)
            yield db
        # Commit succeeded — run callbacks
        for cb in callbacks:
            if inspect.iscoroutinefunction(cb):
                await cb()
            else:
                result = cb()
                if inspect.iscoroutine(result):
                    await result
    finally:
        # Always restore ContextVars — even if commit or a callback raises
        if tok_session is not None:
            _current_session.reset(tok_session)
        if tok_callbacks is not None:
            _on_commit_callbacks.reset(tok_callbacks)


def non_atomic(func):
    """Mark a function as explicitly not requiring a transaction (no-op marker)."""
    func._non_atomic = True
    return func


async def on_commit(func):
    """
    Schedule a callback to run after the current transaction commits.

    If called inside an ``async with atomic():`` block, the callback is deferred
    until the block's commit succeeds.  If called outside any atomic block,
    the callback runs immediately (as it does outside a
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


def atomic(func=None):
    """
    Wrap code in a database transaction.

    As a context manager::

        async with atomic():
            await Post.objects.create(title="Hello")

    As a decorator::

        @atomic
        async def create_post(title):
            post = await Post.objects.create(title=title)
            return post
    """
    if func is not None:
        # Used as @atomic (bare, without parentheses)
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            async with _atomic_cm():
                return await func(*args, **kwargs)
        return wrapper
    # Used as async with atomic():
    return _atomic_cm()
