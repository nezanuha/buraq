import itertools
from collections.abc import AsyncGenerator
from contextvars import ContextVar

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

# Context var tracking the active session inside an atomic() block.
# None when no atomic block is active.
_current_session: ContextVar[AsyncSession | None] = ContextVar(
    "_current_session", default=None
)

# Context var collecting on_commit callbacks registered inside an atomic() block.
# None when no atomic block is active (callbacks run immediately in that case).
_on_commit_callbacks: ContextVar[list | None] = ContextVar(
    "_on_commit_callbacks", default=None
)


#: The async driver to recommend for each backend, and the extra that installs it.
_ASYNC_DRIVERS = {
    "sqlite": ("aiosqlite", None),
    "postgresql": ("asyncpg", "postgres"),
    "postgres": ("asyncpg", "postgres"),
    "mysql": ("aiomysql", "mysql"),
    "mariadb": ("aiomysql", "mysql"),
}

#: Drivers that exist but block. Naming one is the same mistake as naming none.
_SYNC_DRIVERS = frozenset({
    "pysqlite", "psycopg2", "psycopg2cffi", "pymysql", "mysqldb",
    "mysqlconnector", "cx_oracle", "pyodbc",
})


def _check_database_url(url: str) -> None:
    """Fail with something worth reading when DATABASE_URL names a blocking driver.

    SQLAlchemy catches this on its own, but not always legibly: a bare
    ``postgresql://`` raises ``ModuleNotFoundError: No module named 'psycopg2'``,
    which reads like a missing dependency. It is not -- psycopg2 cannot be
    awaited, so installing it does not help. The driver has to change.
    """
    from buraq.exceptions import ImproperlyConfigured

    scheme = url.split("://", 1)[0].lower()
    backend, _, driver = scheme.partition("+")

    if driver and driver not in _SYNC_DRIVERS:
        return                              # async, or a driver we do not know

    suggested, extra = _ASYNC_DRIVERS.get(backend, (None, None))
    if suggested is None:
        if driver:                          # blocking, on a backend we cannot advise on
            raise ImproperlyConfigured(
                f"DATABASE_URL uses {driver!r}, which is a blocking driver. Buraq "
                f"is async throughout and needs one that can be awaited."
            )
        return

    install = f"\n\nInstall it with:  pip install buraq[{extra}]" if extra else ""
    raise ImproperlyConfigured(
        f"DATABASE_URL is {scheme!r}, which selects a blocking driver. Buraq is "
        f"async throughout, so the driver has to be one that can be awaited."
        f"\n\nUse:  {backend}+{suggested}://...{install}"
    )


def _make_engine(alias: str = "default"):
    from buraq.conf import settings

    url, options = database_config(alias)
    _check_database_url(url)

    kwargs = dict(echo=settings.DATABASE_ECHO, pool_pre_ping=True)
    if url.startswith("sqlite"):
        # One connection reused, so pool sizing and recycling do not apply --
        # StaticPool rejects them outright.
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = StaticPool
    else:
        kwargs["pool_size"] = getattr(settings, "DATABASE_POOL_SIZE", 10)
        kwargs["max_overflow"] = getattr(settings, "DATABASE_MAX_OVERFLOW", 20)
        # MySQL drops an idle connection after eight hours by default, and
        # pool_pre_ping only discovers that by paying a round trip on checkout.
        # Recycling retires the connection before it goes stale instead.
        kwargs["pool_recycle"] = getattr(settings, "DATABASE_POOL_RECYCLE", 3600)

    # connect_args is merged rather than replaced: overwriting it wholesale
    # would silently drop check_same_thread and break SQLite.
    connect_args = {**kwargs.get("connect_args", {}), **(options.pop("connect_args", None) or {})}
    kwargs.update(options)
    if connect_args:
        kwargs["connect_args"] = connect_args
    return create_async_engine(url, **kwargs)


class _LazyEngine:
    """Lazy proxy — engine is created on first access so settings can be overridden first."""

    def __init__(self, alias: str = "default"):
        self.alias = alias
        self._engine = None
        self._session_factory = None

    def _init(self):
        if self._engine is None:
            self._engine = _make_engine(self.alias)
            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

    def reset(self) -> None:
        """Forget the engine, so the next use builds one from current settings."""
        self._engine = None
        self._session_factory = None

    def __call__(self, *args, **kwargs):
        self._init()
        return self._session_factory(*args, **kwargs)

    def __getattr__(self, name):
        self._init()
        return getattr(self._engine, name)


DEFAULT_DB_ALIAS = "default"

#: One lazy engine per configured alias, built on first use.
_connections: dict[str, "_LazyEngine"] = {}

#: Position in the replica list, so consecutive reads spread across them.
_replica_turn = itertools.count()


def database_config(alias: str = DEFAULT_DB_ALIAS) -> tuple[str, dict]:
    """The URL and engine options for *alias*.

    An entry in DATABASES is either the URL on its own, or a mapping with a
    ``URL`` and an ``OPTIONS`` dict handed straight to SQLAlchemy. The second
    form exists because no fixed set of settings covers what a driver needs:
    asyncpg behind PgBouncer needs ``statement_cache_size=0`` or its prepared
    statements break, SQLite under concurrent writers needs a ``timeout``, and
    naming each of those forever is a losing game.
    """
    entry = _database_entries()[alias]
    if isinstance(entry, str):
        return entry, {}

    from buraq.exceptions import ImproperlyConfigured

    if "URL" not in entry:
        raise ImproperlyConfigured(
            f"DATABASES[{alias!r}] has no 'URL'. Give it the URL on its own, or a "
            f"mapping with 'URL' and optionally 'OPTIONS'."
        )
    unknown = set(entry) - {"URL", "OPTIONS"}
    if unknown:
        raise ImproperlyConfigured(
            f"DATABASES[{alias!r}] has unexpected {sorted(unknown)}. Only 'URL' and "
            f"'OPTIONS' are read; driver settings belong inside 'OPTIONS'."
        )
    return entry["URL"], dict(entry.get("OPTIONS") or {})


def _database_entries() -> dict:
    """Whatever DATABASES holds, or DATABASE_URL as the sole entry."""
    from buraq.conf import settings

    configured = dict(getattr(settings, "DATABASES", None) or {})
    if not configured:
        options = dict(getattr(settings, "DATABASE_OPTIONS", None) or {})
        entry = {"URL": settings.DATABASE_URL, "OPTIONS": options}
        return {DEFAULT_DB_ALIAS: entry if options else settings.DATABASE_URL}
    if DEFAULT_DB_ALIAS not in configured:
        from buraq.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured(
            f"DATABASES has no {DEFAULT_DB_ALIAS!r} entry. Every query that does "
            f"not name a database uses it, so there has to be one."
        )
    return configured


def database_urls() -> dict[str, str]:
    """Every configured database's URL, by alias."""
    return {alias: database_config(alias)[0] for alias in _database_entries()}


def connection(alias: str = DEFAULT_DB_ALIAS) -> "_LazyEngine":
    """The engine for *alias*, created on first use."""
    if alias not in _connections:
        urls = database_urls()
        if alias not in urls:
            from buraq.exceptions import ImproperlyConfigured

            known = ", ".join(sorted(urls)) or "none"
            raise ImproperlyConfigured(
                f"No database named {alias!r} is configured. Known: {known}."
            )
        _connections[alias] = _LazyEngine(alias)
    return _connections[alias]


def read_alias() -> str:
    """The database a read should go to.

    Replicas are behind the primary by however long replication takes, so this
    is only correct for a query whose caller has not just written something it
    expects to read back. Inside atomic() the writer is used instead, which is
    where that case actually arises -- see routing_alias().
    """
    from buraq.conf import settings

    replicas = [
        alias
        for alias in (getattr(settings, "DATABASE_READ_REPLICAS", None) or [])
        if alias != DEFAULT_DB_ALIAS
    ]
    if not replicas:
        return DEFAULT_DB_ALIAS
    return replicas[next(_replica_turn) % len(replicas)]


def routing_alias(*, write: bool, using: str | None = None) -> str:
    """Which database this query belongs on.

    An explicit using() wins. Otherwise a write goes to the primary, and so does
    a read inside an atomic block: a transaction that has written a row and then
    reads it back must not be answered by a replica that has not seen the write
    yet.
    """
    if using is not None:
        return using
    if write or _current_session.get() is not None:
        return DEFAULT_DB_ALIAS
    return read_alias()


def session_for(alias: str | None = None):
    """An async_sessionmaker-compatible callable for *alias*."""
    return connection(alias or DEFAULT_DB_ALIAS)


def reset_connections() -> None:
    """Forget every engine, so the next use reads settings again.

    The default connection is reset in place rather than replaced: SessionLocal
    is bound to that object at import time throughout the framework, and handing
    out a new one would leave those references pointing at a dead engine.
    """
    for alias in [a for a in _connections if a != DEFAULT_DB_ALIAS]:
        del _connections[alias]
    _connections[DEFAULT_DB_ALIAS].reset()


_lazy = _LazyEngine(DEFAULT_DB_ALIAS)
_connections[DEFAULT_DB_ALIAS] = _lazy
engine = _lazy  # kept for backwards compat
SessionLocal = _lazy  # async_sessionmaker-compatible callable


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def unmanaged_table_names() -> set[str]:
    """
    Tables owned by models with ``Meta.managed = False``.

    Buraq never creates, alters or drops these — they represent existing tables
    or database views maintained outside the ORM.
    """
    names = set()
    for mapper in Base.registry.mappers:
        opts = getattr(mapper.class_, "_meta", None)
        if opts is not None and not opts.managed:
            names.add(mapper.class_.__tablename__)
    return names


#: Contrib apps whose migrations ship with Buraq. Each owns an Alembic branch
#: under buraq/contrib/<app>/migrations and is applied only when the app
#: is installed. Extend this when another contrib app gains migrations.
APPS_WITH_MIGRATIONS = (
    "auth",
    "contenttypes",
    "flatpages",
    "redirects",
    "sessions",
    "sites",
)


def app_table_names(app: str) -> set[str]:
    """
    The tables whose models live in ``app``.

    Which app owns a table is what lets a migration be written into that app's
    own directory rather than a single pile shared by the whole project. A model
    is owned by the app whose package its module sits in.
    """
    names = set()
    for mapper in Base.registry.mappers:
        module = mapper.class_.__module__ or ""
        if module == app or module.startswith(f"{app}."):
            table = getattr(mapper.class_, "__tablename__", None)
            if table:
                names.add(table)
    return names


def framework_table_names() -> set[str]:
    """
    Tables whose migrations Buraq ships, so a project must never generate them.

    Without this a project's autogenerate would emit create_table for the
    framework's own schema, duplicating what the shipped branch already applies.
    """
    names = set()
    for app in APPS_WITH_MIGRATIONS:
        names |= app_table_names(f"buraq.contrib.{app}")
    return names


def migration_version_locations() -> list[str]:
    """
    The Alembic version locations an installed set of apps requires.

    Alembic resolves ``package:path`` against the installed package, so these
    are read out of Buraq itself rather than copied into the project -- which
    is why a project needs no alembic.ini of its own. Only installed apps are
    listed; an app that is not installed must not have its tables created.
    """
    from buraq.conf import settings

    installed = set(getattr(settings, "INSTALLED_APPS", None) or [])
    locations = []
    for app in APPS_WITH_MIGRATIONS:
        dotted = f"buraq.contrib.{app}"
        if any(entry == dotted or entry.startswith(f"{dotted}.") for entry in installed):
            locations.append(f"{dotted}:migrations")
    return locations


def tables_migrations_ignore() -> set[str]:
    """
    Tables migration autogeneration must leave alone.

    Three kinds: models declaring ``Meta.managed = False``; the table Buraq's
    database cache backend creates with raw SQL, which never appears in
    ``Base.metadata`` so autogenerate would treat it as a table to drop; and the
    framework's own tables, whose migrations ship with Buraq.
    """
    from buraq.conf import settings

    return (
        unmanaged_table_names()
        | framework_table_names()
        | {
            getattr(settings, "CACHE_TABLE", None) or "buraq_cache_table",
        }
    )


async def create_tables() -> None:
    _lazy._init()
    unmanaged = unmanaged_table_names()
    tables = [t for name, t in Base.metadata.tables.items() if name not in unmanaged]
    async with _lazy._engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
