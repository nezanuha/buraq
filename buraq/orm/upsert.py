"""
Inserting rows that may already be there, in each database's spelling.

Every database can do this and no two agree on how. Postgres and SQLite have
``ON CONFLICT DO NOTHING``; MySQL has never had it, and wants
``ON DUPLICATE KEY UPDATE`` instead.

The call sites picked the right dialect's ``insert()`` and then called
``on_conflict_do_nothing()`` on all three, which MySQL's ``Insert`` does not
have -- so adding to a many-to-many relation raised ``AttributeError: 'Insert'
object has no attribute 'on_conflict_do_nothing'`` on MySQL, and only there.
"""
from __future__ import annotations

from typing import Any

__all__ = ["insert_ignoring_duplicates"]


def _dialect_name(url: str) -> str:
    from sqlalchemy.engine import make_url

    try:
        return make_url(url).get_dialect().name
    except Exception:  # pragma: no cover - an unparseable URL fails later anyway
        return "postgresql"


def insert_ignoring_duplicates(table, rows: list[dict[str, Any]], url: str):
    """An INSERT that leaves rows already present alone.

    Used where the row is the fact -- a link in an association table, a record
    being restored -- so a second insert of the same one is not an error worth
    raising.
    """
    dialect = _dialect_name(url)

    if dialect in ("mysql", "mariadb"):
        from sqlalchemy.dialects.mysql import insert as mysql_insert

        statement = mysql_insert(table).values(rows)
        # MySQL has no DO NOTHING. Setting a key column to the value it already
        # has is the usual way to spell it: the row is matched, nothing about it
        # changes. INSERT IGNORE would also work and would swallow unrelated
        # errors -- a truncated value, a bad foreign key -- along with the
        # duplicate, which is too much to discard for the convenience.
        columns = list(table.primary_key.columns) or list(table.columns)
        name = columns[0].name
        return statement.on_duplicate_key_update(
            {name: getattr(statement.inserted, name)}
        )

    if dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        return sqlite_insert(table).values(rows).on_conflict_do_nothing()

    from sqlalchemy.dialects.postgresql import insert as postgresql_insert

    return postgresql_insert(table).values(rows).on_conflict_do_nothing()
