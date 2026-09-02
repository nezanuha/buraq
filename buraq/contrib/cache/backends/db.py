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


#: Ten years. The row format stores an expiry, so "never" needs a stand-in.
_FOREVER = 10 * 365 * 24 * 3600


def _for_update(sql: str, session) -> str:
    """Add row locking, where the database has it.

    SQLite has no SELECT ... FOR UPDATE -- it locks the whole database for a
    write transaction instead, which gives the same guarantee by a blunter
    route. Postgres and MySQL both need it asked for.
    """
    dialect = getattr(getattr(session, "bind", None), "dialect", None)
    name = getattr(dialect, "name", "")
    if name in ("postgresql", "mysql", "mariadb"):
        return f"{sql} FOR UPDATE"
    return sql


class DatabaseCache(BaseCacheBackend):
    """Cache backend that persists entries in a database table."""

    def __init__(
        self,
        table: str | None = None,
        *,
        location: str | None = None,
        key_prefix: str | None = None,
        timeout: int | None = None,
        version: int | None = None,
        cull_probability: float | None = None,
        **kwargs,
    ):
        """``location`` is the table name when it comes from a CACHES entry,
        which is what it means for Django's database cache."""
        self._init_shared(key_prefix, timeout, version)
        if table is None:
            table = location
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
            [self._make_key(key), now],
        )
        if not rows:
            return None
        try:
            return self._deserialize(rows[0][0])
        except Exception:
            return None

    async def set(self, key: str, value: Any, timeout: int | None = None) -> None:
        import random

        import sqlalchemy as sa
        timeout = self._resolve_timeout(timeout)
        expires = time.time() + (timeout if timeout and timeout > 0 else _FOREVER)
        raw = self._serialize(value)
        # Upsert via DELETE + INSERT in a single transaction for atomicity
        from buraq.core.db import SessionLocal
        async with SessionLocal() as db:
            stored = self._make_key(key)
            await db.execute(
                sa.text(f"DELETE FROM {self._table} WHERE cache_key = :0"),
                {"0": stored},
            )
            await db.execute(
                sa.text(
                    f"INSERT INTO {self._table} (cache_key, value, expires) VALUES (:0, :1, :2)"
                ),
                {"0": stored, "1": raw, "2": expires},
            )
            await db.commit()
        if self._cull_probability and random.random() < self._cull_probability:
            await self.cull()

    async def delete(self, key: str) -> None:
        await self._execute(
            f"DELETE FROM {self._table} WHERE cache_key = :0", [self._make_key(key)]
        )

    async def exists(self, key: str) -> bool:
        now = time.time()
        rows = await self._fetch(
            f"SELECT 1 FROM {self._table} WHERE cache_key = :0 AND expires > :1 LIMIT 1",
            [self._make_key(key), now],
        )
        return bool(rows)

    async def clear(self) -> None:
        """Delete this cache's rows.

        Scoped to the key prefix when there is one: two caches sharing a table
        and told apart by their prefix must not wipe each other.
        """
        if self._prefix:
            await self._execute(
                f"DELETE FROM {self._table} WHERE cache_key LIKE :0",
                [f"{self._prefix}%"],
            )
        else:
            await self._execute(f"DELETE FROM {self._table}")

    async def add(self, key: str, value: Any, timeout: int | None = None) -> bool:
        """Set the key only if it is not already there.

        The primary key on cache_key does the deciding: a second INSERT of the
        same key fails, so exactly one caller wins even when several try at
        once. The inherited version checks and then inserts, and two callers can
        both find the key missing -- which defeats the point, since `add` is what
        people build locks out of.
        """
        import sqlalchemy as sa
        from sqlalchemy.exc import IntegrityError

        from buraq.core.db import SessionLocal

        timeout = self._resolve_timeout(timeout)
        expires = time.time() + (timeout if timeout and timeout > 0 else _FOREVER)
        stored = self._make_key(key)
        now = time.time()

        async with SessionLocal() as db:
            # An expired row still holds the key, so clear it first -- otherwise
            # a lock could never be taken again once it had expired.
            await db.execute(
                sa.text(
                    f"DELETE FROM {self._table} "
                    f"WHERE cache_key = :0 AND expires <= :1"
                ),
                {"0": stored, "1": now},
            )
            try:
                await db.execute(
                    sa.text(
                        f"INSERT INTO {self._table} (cache_key, value, expires) "
                        f"VALUES (:0, :1, :2)"
                    ),
                    {"0": stored, "1": self._serialize(value), "2": expires},
                )
                await db.commit()
            except IntegrityError:
                await db.rollback()
                return False
        return True

    async def incr(self, key: str, delta: int = 1) -> int:
        """Add to the integer at the key, in one statement.

        The inherited version reads, adds and writes back, and both halves wait
        on the database, so concurrent callers all read the same value and all
        write the same result -- 500 increments landing as 1. Letting the
        database do the addition means one row lock and no lost counts.

        The value column holds a pickle, so the arithmetic cannot happen in SQL
        on it; the row is locked for the length of the transaction instead and
        the read and write happen inside that.
        """
        import sqlalchemy as sa

        from buraq.core.db import SessionLocal

        stored = self._make_key(key)
        now = time.time()
        async with SessionLocal() as db:
            locked = _for_update(
                f"SELECT value, expires FROM {self._table} "
                f"WHERE cache_key = :0 AND expires > :1",
                db,
            )
            row = (await db.execute(sa.text(locked), {"0": stored, "1": now})).first()
            if row is None:
                await db.rollback()
                raise ValueError(f"Cache key {key!r} not found.")

            new_value = int(self._deserialize(row[0])) + delta
            await db.execute(
                sa.text(f"UPDATE {self._table} SET value = :1 WHERE cache_key = :0"),
                {"0": stored, "1": self._serialize(new_value)},
            )
            await db.commit()
        return new_value

    async def cull(self) -> int:
        """Remove expired entries. Returns count deleted."""
        now = time.time()
        result = await self._execute(
            f"DELETE FROM {self._table} WHERE expires <= :0", [now]
        )
        return getattr(result, "rowcount", 0)
