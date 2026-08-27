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
