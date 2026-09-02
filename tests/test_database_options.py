"""
OPTIONS is the escape hatch for anything the driver needs and Buraq has no name for.

Without it a driver setting can only be reached if Buraq happens to expose a
setting for it, which is a losing game: asyncpg behind PgBouncer needs
``statement_cache_size=0`` or its prepared statements break, and SQLite under
concurrent writers needs a ``timeout``. Neither had a way in.
"""

import pytest

import buraq.core.db as db
from buraq.conf import settings
from buraq.exceptions import ImproperlyConfigured


@pytest.fixture
def engine_kwargs(monkeypatch):
    """Capture what _make_engine hands to SQLAlchemy, without a driver installed."""
    seen = {}

    def fake_create(url, **kw):
        seen.clear()
        seen.update(kw, URL=url)
        return object()

    monkeypatch.setattr(db, "create_async_engine", fake_create)
    monkeypatch.setattr(settings, "DATABASES", {}, raising=False)
    monkeypatch.setattr(settings, "DATABASE_OPTIONS", {}, raising=False)

    def build(alias="default"):
        db._make_engine(alias)
        return dict(seen)

    return build


def test_options_reach_the_engine(engine_kwargs, monkeypatch):
    monkeypatch.setattr(settings, "DATABASES", {
        "default": {
            "URL": "postgresql+asyncpg://u:p@h/db",
            "OPTIONS": {"pool_size": 20, "isolation_level": "SERIALIZABLE"},
        },
    }, raising=False)
    kw = engine_kwargs()
    assert kw["pool_size"] == 20, "an explicit pool size must beat the default"
    assert kw["isolation_level"] == "SERIALIZABLE"


def test_connect_args_are_merged_not_replaced(engine_kwargs, monkeypatch):
    """Replacing them wholesale would drop check_same_thread and break SQLite."""
    monkeypatch.setattr(settings, "DATABASES", {
        "default": {
            "URL": "sqlite+aiosqlite:///./t.db",
            "OPTIONS": {"connect_args": {"timeout": 20}},
        },
    }, raising=False)
    kw = engine_kwargs()
    assert kw["connect_args"] == {"check_same_thread": False, "timeout": 20}


def test_the_pgbouncer_flag_can_be_set(engine_kwargs, monkeypatch):
    """asyncpg in a transaction pool needs this, and it had no way in before."""
    monkeypatch.setattr(settings, "DATABASES", {
        "default": {
            "URL": "postgresql+asyncpg://u:p@h/db",
            "OPTIONS": {"connect_args": {"statement_cache_size": 0}},
        },
    }, raising=False)
    assert engine_kwargs()["connect_args"]["statement_cache_size"] == 0


def test_each_database_has_its_own_options(engine_kwargs, monkeypatch):
    """A replica takes the reads, so it wants a different pool from the primary."""
    monkeypatch.setattr(settings, "DATABASES", {
        "default": {"URL": "postgresql+asyncpg://u:p@a/db", "OPTIONS": {"pool_size": 20}},
        "replica": {"URL": "postgresql+asyncpg://u:p@b/db", "OPTIONS": {"pool_size": 50}},
    }, raising=False)
    assert engine_kwargs("default")["pool_size"] == 20
    assert engine_kwargs("replica")["pool_size"] == 50


def test_database_url_form_takes_options_too(engine_kwargs, monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "mysql+aiomysql://u:p@h/db", raising=False)
    monkeypatch.setattr(settings, "DATABASE_OPTIONS", {"pool_size": 5}, raising=False)
    assert engine_kwargs()["pool_size"] == 5


def test_a_plain_url_string_still_works(engine_kwargs, monkeypatch):
    monkeypatch.setattr(settings, "DATABASES", {
        "default": "sqlite+aiosqlite:///./t.db",
    }, raising=False)
    assert engine_kwargs()["URL"] == "sqlite+aiosqlite:///./t.db"


# ── Pool recycling ───────────────────────────────────────────────────────────

def test_connections_are_recycled_before_mysql_drops_them(engine_kwargs, monkeypatch):
    """MySQL closes an idle connection after eight hours; retire it first."""
    monkeypatch.setattr(settings, "DATABASE_URL", "mysql+aiomysql://u:p@h/db", raising=False)
    kw = engine_kwargs()
    assert kw["pool_recycle"] == 3600
    assert kw["pool_recycle"] < 8 * 3600


def test_sqlite_gets_no_pool_sizing(engine_kwargs, monkeypatch):
    """StaticPool reuses one connection and rejects pool arguments outright."""
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///./t.db", raising=False)
    kw = engine_kwargs()
    assert "pool_size" not in kw and "pool_recycle" not in kw


# ── Bad configuration ────────────────────────────────────────────────────────

def test_a_mapping_without_a_url_says_so(monkeypatch):
    monkeypatch.setattr(settings, "DATABASES", {"default": {"OPTIONS": {}}}, raising=False)
    with pytest.raises(ImproperlyConfigured, match="URL"):
        db.database_config("default")


def test_a_stray_key_is_not_silently_ignored(monkeypatch):
    """Driver settings put beside URL rather than inside OPTIONS would do nothing."""
    monkeypatch.setattr(settings, "DATABASES", {
        "default": {"URL": "sqlite+aiosqlite:///./t.db", "pool_size": 20},
    }, raising=False)
    with pytest.raises(ImproperlyConfigured, match="pool_size"):
        db.database_config("default")


# --- pool sizing that the chosen pool cannot take ----------------------------


def test_pool_sizing_is_left_out_for_a_pool_that_has_none():
    """
    NullPool opens a connection per use and holds none, so pool_size and
    max_overflow mean nothing to it -- and SQLAlchemy refuses them rather than
    ignoring them:

        TypeError: Invalid argument(s) 'pool_size','max_overflow' sent to
        create_engine(), using configuration PGDialect_asyncpg/NullPool/Engine

    So DATABASE_OPTIONS = {"poolclass": NullPool} -- what a project sets to hand
    pooling to PgBouncer -- could not start at all.
    """
    from sqlalchemy.pool import NullPool

    from buraq.core.db import _drop_pool_sizing_if_unused

    kwargs = {"poolclass": NullPool, "pool_size": 10, "max_overflow": 20, "echo": False}
    _drop_pool_sizing_if_unused(kwargs)

    assert sorted(kwargs) == ["echo", "poolclass"]


def test_pool_sizing_is_kept_for_a_pool_that_uses_it():
    from sqlalchemy.pool import QueuePool

    from buraq.core.db import _drop_pool_sizing_if_unused

    kwargs = {"poolclass": QueuePool, "pool_size": 10, "max_overflow": 20}
    _drop_pool_sizing_if_unused(kwargs)

    assert kwargs["pool_size"] == 10
    assert kwargs["max_overflow"] == 20


def test_nothing_is_dropped_when_no_pool_was_chosen():
    """The default pool takes them, and guessing otherwise would silently
    discard a project's tuning."""
    from buraq.core.db import _drop_pool_sizing_if_unused

    kwargs = {"pool_size": 10, "max_overflow": 20}
    _drop_pool_sizing_if_unused(kwargs)

    assert kwargs == {"pool_size": 10, "max_overflow": 20}


def test_a_pool_taking_arbitrary_keywords_keeps_them():
    """Asked of the class rather than from a list, which would go stale the
    moment SQLAlchemy adds a pool."""
    from buraq.core.db import _pool_accepts

    class _Anything:
        def __init__(self, creator, **kw):
            pass

    assert _pool_accepts(_Anything, "pool_size") is True
