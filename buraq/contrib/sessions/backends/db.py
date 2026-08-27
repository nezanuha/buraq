"""
Database-backed session backend.

Stores session data in a ``buraq_sessions`` table, which arrives with the app's
own migration -- add ``buraq.contrib.sessions`` to INSTALLED_APPS and run
``buraq migrate``. It used to be a block of CREATE TABLE in this docstring for
you to run by hand, which was the one table Buraq owned that it would not
create for you.

Settings::

    INSTALLED_APPS = [..., "buraq.contrib.sessions"]
    SESSION_ENGINE = "buraq.contrib.sessions.backends.db"
"""
from __future__ import annotations

import time

from buraq.contrib.sessions.backends.base import SessionBase

_TABLE = "buraq_sessions"


def _explain_missing_table(exc: Exception) -> None:
    """
    Turn "no such table: buraq_sessions" into something actionable.

    The table arrives with the app's migration, so the cause is almost always
    that the app is not installed -- which the database driver has no way to
    know and no way to say.
    """
    from buraq.exceptions import ImproperlyConfigured

    text = str(exc).lower()
    if _TABLE in text and ("no such table" in text or "does not exist" in text):
        raise ImproperlyConfigured(
            f"SESSION_ENGINE uses the database backend, but the {_TABLE!r} table "
            "does not exist. Add 'buraq.contrib.sessions' to INSTALLED_APPS and "
            "run `buraq migrate`."
        ) from exc


class DatabaseSessionBackend(SessionBase):
    """Stores session data in the database."""

    async def _execute(self, sql: str, params: dict):
        import sqlalchemy as sa

        from buraq.core.db import SessionLocal
        async with SessionLocal() as db:
            try:
                result = await db.execute(sa.text(sql), params)
            except Exception as exc:
                _explain_missing_table(exc)
                raise
            await db.commit()
            return result

    async def _fetch_one(self, sql: str, params: dict):
        import sqlalchemy as sa

        from buraq.core.db import SessionLocal
        async with SessionLocal() as db:
            try:
                result = await db.execute(sa.text(sql), params)
            except Exception as exc:
                _explain_missing_table(exc)
                raise
            return result.fetchone()

    async def exists(self, session_key: str) -> bool:
        row = await self._fetch_one(
            f"SELECT 1 FROM {_TABLE} WHERE session_key = :key AND expire_date > :now",
            {"key": session_key, "now": time.time()},
        )
        return row is not None

    async def load(self) -> dict:
        row = await self._fetch_one(
            f"SELECT session_data, expire_date FROM {_TABLE} WHERE session_key = :key",
            {"key": self._session_key},
        )
        if row is None or row[1] < time.time():
            if row is not None:
                await self.delete()
            self._session_key = None
            return {}
        return self._decode(row[0])

    async def save(self, must_create: bool = False) -> None:
        key = await self._get_or_create_session_key()
        if must_create and await self.exists(key):
            raise ValueError(f"Session key {key!r} already exists.")

        data = self._encode(self._session_cache or {})
        expires = self.get_expiry_date()

        await self._execute(
            f"DELETE FROM {_TABLE} WHERE session_key = :key",
            {"key": key},
        )
        await self._execute(
            f"INSERT INTO {_TABLE} (session_key, session_data, expire_date) "
            "VALUES (:key, :data, :expires)",
            {"key": key, "data": data, "expires": expires},
        )

    async def delete(self, session_key: str | None = None) -> None:
        key = session_key or self._session_key
        if key:
            await self._execute(
                f"DELETE FROM {_TABLE} WHERE session_key = :key",
                {"key": key},
            )

    async def clear_expired(self) -> int:
        result = await self._execute(
            f"DELETE FROM {_TABLE} WHERE expire_date < :now",
            {"now": time.time()},
        )
        return getattr(result, "rowcount", 0)
