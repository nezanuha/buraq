"""
Shared test configuration.

The settings layer refuses to import with a default/insecure SECRET_KEY, and
`.env` is gitignored — so a fresh clone could not run `pytest` at all until the
developer hand-created one. Setting the environment here keeps the suite
hermetic: no `.env`, no local database, no external state required.

Must run before any `buraq` import, so this file only touches os.environ at
module level and imports nothing from the package.
"""

import os

import pytest

os.environ.setdefault("SECRET_KEY", "test-only-secret-key-not-used-outside-the-suite")
os.environ.setdefault("DEBUG", "True")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

#: The database the suite runs against. Defaults to in-memory SQLite, so a fresh
#: clone needs nothing installed; CI overrides it to exercise the same tests
#: against PostgreSQL and MySQL. Tests that need a real database should use this
#: rather than naming a URL, or they only ever prove SQLite works.
TEST_DATABASE_URL = os.environ["DATABASE_URL"]


def use_test_database(settings) -> None:
    """Point *settings* at the database under test and forget any stale engine.

    The engine is built once and cached, so setting DATABASE_URL after something
    has already connected leaves the old engine in place -- which went unnoticed
    while every test used the same in-memory SQLite.
    """
    from buraq.core.db import reset_connections

    settings.DATABASE_URL = TEST_DATABASE_URL
    settings.DATABASES = {}
    reset_connections()


@pytest.fixture(scope="session", autouse=True)
def _database_lifecycle():
    """Keep connections inside the loop that opened them, and close what is left.

    pytest-asyncio gives each test its own event loop, and a pooled connection
    belongs to the loop that opened it. Handing one to the next test is what
    "Event loop is closed" means, and it is why the PostgreSQL and MySQL jobs
    failed while every SQLite one passed: aiosqlite has no socket to strand.

    NullPool opens and closes a connection per use, so none outlives its loop.
    That is slower and exactly wrong for production -- where the process has one
    loop and pooling is the point -- so it is set here rather than in the
    framework.

    SQLite is left alone: its in-memory database exists only for as long as the
    one connection holding it, which is why that backend pins StaticPool.

    The teardown closes the last engine, which nothing resets and so nothing
    ever closed -- its connections were finalised at interpreter shutdown, after
    the loop had gone.
    """
    from buraq.conf import settings
    from buraq.core.db import reset_connections

    if not TEST_DATABASE_URL.startswith("sqlite"):
        from sqlalchemy.pool import NullPool

        settings.DATABASE_OPTIONS = {
            **(getattr(settings, "DATABASE_OPTIONS", None) or {}),
            "poolclass": NullPool,
        }
        reset_connections()

    yield

    reset_connections()
