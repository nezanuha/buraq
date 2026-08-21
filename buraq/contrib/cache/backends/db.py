"""
Database-backed cache backend.

Stores cached values in a database table. Create the table with::

    buraq createcachetable

Or manually::

    CREATE TABLE buraq_cache_table (
        cache_key VARCHAR(255) NOT NULL PRIMARY KEY,
        value     TEXT         NOT NULL,
        expires   DOUBLE PRECISION NOT NULL
    );

Usage::

    CACHE_BACKEND = "buraq.contrib.cache.backends.db.DatabaseCache"
    CACHE_TABLE   = "buraq_cache_table"
"""
from __future__ import annotations

import json
import pickle
import re
import time
from typing import Any

from buraq.contrib.cache.backends.base import BaseCacheBackend
from buraq.exceptions import ImproperlyConfigured

DEFAULT_TABLE = "buraq_cache_table"


def _checked_table_name(name: str) -> str:
    """
    Reject anything that is not a plain SQL identifier.

    A table name cannot be a bound parameter, so it is interpolated into the
    statements below. The value comes from settings rather than from a request,
    which makes this a guard rather than a fix -- but a setting read from an
    environment variable is one indirection away from somewhere less trusted,
    and the check costs nothing.
    """
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name or ""):
        raise ImproperlyConfigured(
            f"CACHE_TABLE must be a plain identifier (letters, digits, underscore); "
            f"got {name!r}."
        )
    return name


class DatabaseCache(BaseCacheBackend):
    """Cache backend that persists entries in a database table."""

    def __init__(
        self, table: str | None = None, *, cull_probability: float | None = None, **kwargs
    ):
        if table is None:
            # Falls back to the setting so CACHE_TABLE actually takes effect; an
            # explicit table (from CACHES OPTIONS) still wins.
            try:
                from buraq.conf import settings
                table = getattr(settings, "CACHE_TABLE", None) or DEFAULT_TABLE
            except Exception:
                table = DEFAULT_TABLE
        self._table = _checked_table_name(table)
        if cull_probability is None:
            try:
                from buraq.conf import settings
                cull_probability = getattr(settings, "CACHE_CULL_PROBABILITY", 0.1)
            except Exception:
                cull_probability = 0.1
        self._cull_probability = cull_probability

    @staticmethod
    def _bind(params: tuple | list) -> dict:
        return {str(i): v for i, v in enumerate(params)} if params else {}

    async def _execute(self, sql: str, params: tuple | list = ()):
        import sqlalchemy as sa

        from buraq.core.db import SessionLocal
        async with SessionLocal() as db:
            result = await db.execute(sa.text(sql), self._bind(params))
            await db.commit()
            return result

    async def _fetch(self, sql: str, params: tuple | list = ()):
        import sqlalchemy as sa

        from buraq.core.db import SessionLocal
        async with SessionLocal() as db:
            result = await db.execute(sa.text(sql), self._bind(params))
            return result.fetchall()

    def _serialize(self, value: Any) -> str:
        return json.dumps(pickle.dumps(value).hex())

    def _deserialize(self, raw: str) -> Any:
        return pickle.loads(bytes.fromhex(json.loads(raw)))

    async def get(self, key: str) -> Any | None:
        now = time.time()
        rows = await self._fetch(
            f"SELECT value FROM {self._table} WHERE cache_key = :0 AND expires > :1",
            [key, now],
        )
        if not rows:
            return None
        try:
            return self._deserialize(rows[0][0])
        except Exception:
            return None

    async def set(self, key: str, value: Any, timeout: int | None = 300) -> None:
        import random

        import sqlalchemy as sa
        expires = time.time() + (timeout if timeout is not None else 300)
        raw = self._serialize(value)
        # Upsert via DELETE + INSERT in a single transaction for atomicity
        from buraq.core.db import SessionLocal
        async with SessionLocal() as db:
            await db.execute(sa.text(f"DELETE FROM {self._table} WHERE cache_key = :0"), {"0": key})
            await db.execute(
                sa.text(
                    f"INSERT INTO {self._table} (cache_key, value, expires) VALUES (:0, :1, :2)"
                ),
                {"0": key, "1": raw, "2": expires},
            )
            await db.commit()
        if self._cull_probability and random.random() < self._cull_probability:
            await self.cull()

    async def delete(self, key: str) -> None:
        await self._execute(f"DELETE FROM {self._table} WHERE cache_key = :0", [key])

    async def exists(self, key: str) -> bool:
        now = time.time()
        rows = await self._fetch(
            f"SELECT 1 FROM {self._table} WHERE cache_key = :0 AND expires > :1 LIMIT 1",
            [key, now],
        )
        return bool(rows)

    async def clear(self) -> None:
        await self._execute(f"DELETE FROM {self._table}")

    async def cull(self) -> int:
        """Remove expired entries. Returns count deleted."""
        now = time.time()
        result = await self._execute(
            f"DELETE FROM {self._table} WHERE expires <= :0", [now]
        )
        return getattr(result, "rowcount", 0)
