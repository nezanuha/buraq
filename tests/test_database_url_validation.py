"""
A blocking DATABASE_URL should say so, in words that name the fix.

SQLAlchemy already refuses these, but not always legibly: a bare
``postgresql://`` raises ``ModuleNotFoundError: No module named 'psycopg2'``,
which reads like a missing dependency and sends you to install the one package
that cannot help -- psycopg2 blocks, so it can never be awaited.
"""

import pytest

from buraq.core.db import _check_database_url
from buraq.exceptions import ImproperlyConfigured


@pytest.mark.parametrize(
    "url",
    [
        "sqlite+aiosqlite:///./db.sqlite3",
        "postgresql+asyncpg://u:p@h/db",
        "mysql+aiomysql://u:p@h/db",
        "mariadb+asyncmy://u:p@h/db",
        # Unknown backends are left alone rather than guessed at.
        "cockroachdb+asyncpg://u:p@h/db",
    ],
)
def test_async_urls_pass(url):
    _check_database_url(url)


@pytest.mark.parametrize(
    "url,suggested",
    [
        ("sqlite:///./db.sqlite3", "sqlite+aiosqlite"),
        ("postgresql://u:p@h/db", "postgresql+asyncpg"),
        ("postgres://u:p@h/db", "postgres+asyncpg"),
        ("postgresql+psycopg2://u:p@h/db", "postgresql+asyncpg"),
        ("mysql://u:p@h/db", "mysql+aiomysql"),
        ("mysql+pymysql://u:p@h/db", "mysql+aiomysql"),
    ],
)
def test_blocking_urls_are_rejected_with_the_fix(url, suggested):
    with pytest.raises(ImproperlyConfigured) as exc:
        _check_database_url(url)
    assert suggested in str(exc.value), "the message must name the driver to use"


@pytest.mark.parametrize(
    "url,extra",
    [
        ("postgresql://u:p@h/db", "buraq[postgres]"),
        ("mysql://u:p@h/db", "buraq[mysql]"),
    ],
)
def test_message_names_the_extra_that_installs_the_driver(url, extra):
    with pytest.raises(ImproperlyConfigured) as exc:
        _check_database_url(url)
    assert extra in str(exc.value)


def test_sqlite_needs_no_extra():
    """aiosqlite is a hard dependency, so telling anyone to install it is noise."""
    with pytest.raises(ImproperlyConfigured) as exc:
        _check_database_url("sqlite:///./db.sqlite3")
    assert "pip install" not in str(exc.value)


def test_engine_creation_reports_it(monkeypatch):
    """The check runs where the engine is built, not only when called directly."""
    from buraq.conf import settings
    from buraq.core.db import _make_engine

    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://u:p@h/db", raising=False)
    with pytest.raises(ImproperlyConfigured):
        _make_engine()
