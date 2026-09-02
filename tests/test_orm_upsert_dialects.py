"""
Inserting rows that may already exist, in each database's spelling.

Every database can do this and no two agree how. Postgres and SQLite have
ON CONFLICT DO NOTHING; MySQL has never had it and wants ON DUPLICATE KEY
UPDATE.

The call sites chose the right dialect's `insert()` and then called
`on_conflict_do_nothing()` on all three, which MySQL's Insert does not have. So
adding to a many-to-many relation, and `bulk_create(ignore_conflicts=True)`,
raised on MySQL and only there:

    AttributeError: 'Insert' object has no attribute 'on_conflict_do_nothing'

Nothing here needs a server: the statement is compiled for each dialect, which
is where the difference lives.
"""

import importlib

import pytest
import sqlalchemy as sa

from buraq.orm.upsert import insert_ignoring_duplicates


@pytest.fixture
def association():
    metadata = sa.MetaData()
    return sa.Table(
        "post_tags",
        metadata,
        sa.Column("post_id", sa.Integer, primary_key=True),
        sa.Column("tag_id", sa.Integer, primary_key=True),
    )


def _sql(table, url, module):
    dialect = importlib.import_module(module).dialect()
    statement = insert_ignoring_duplicates(table, [{"post_id": 1, "tag_id": 2}], url)
    return " ".join(str(statement.compile(dialect=dialect)).split())


@pytest.mark.parametrize(
    "url,module,expected",
    [
        (
            "postgresql+asyncpg://u:p@h/db",
            "sqlalchemy.dialects.postgresql",
            "ON CONFLICT DO NOTHING",
        ),
        (
            "sqlite+aiosqlite:///:memory:",
            "sqlalchemy.dialects.sqlite",
            "ON CONFLICT DO NOTHING",
        ),
        (
            "mysql+aiomysql://u:p@h/db",
            "sqlalchemy.dialects.mysql",
            "ON DUPLICATE KEY UPDATE",
        ),
        (
            "mysql+aiomysql://u:p@h/db?charset=utf8mb4",
            "sqlalchemy.dialects.mysql",
            "ON DUPLICATE KEY UPDATE",
        ),
    ],
)
def test_each_dialect_gets_its_own_spelling(association, url, module, expected):
    assert expected in _sql(association, url, module)


def test_mysql_updates_a_key_column_to_the_value_it_already_has(association):
    """
    A no-op update is how MySQL spells "leave it alone". INSERT IGNORE would
    also work and would swallow a truncated value or a bad foreign key along
    with the duplicate, which is too much to discard for the convenience.
    """
    sql = _sql(association, "mysql+aiomysql://u:p@h/db", "sqlalchemy.dialects.mysql")
    assert "ON DUPLICATE KEY UPDATE post_id = VALUES(post_id)" in sql


def test_mariadb_is_treated_as_mysql(association):
    sql = _sql(association, "mariadb+aiomysql://u:p@h/db", "sqlalchemy.dialects.mysql")
    assert "ON DUPLICATE KEY UPDATE" in sql


def test_a_table_without_a_primary_key_still_works():
    """Falls back to the first column, so a log or through-table with no key
    declared does not crash the statement builder."""
    metadata = sa.MetaData()
    table = sa.Table("plain", metadata, sa.Column("a", sa.Integer))
    dialect = importlib.import_module("sqlalchemy.dialects.mysql").dialect()
    statement = insert_ignoring_duplicates(table, [{"a": 1}], "mysql://u:p@h/db")

    assert "ON DUPLICATE KEY UPDATE" in str(statement.compile(dialect=dialect))


def test_an_unparseable_url_does_not_raise():
    """A bad URL fails when something tries to connect, with a better message
    than one from here."""
    metadata = sa.MetaData()
    table = sa.Table("t", metadata, sa.Column("a", sa.Integer, primary_key=True))

    assert insert_ignoring_duplicates(table, [{"a": 1}], "not a url") is not None
