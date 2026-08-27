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


def _make_engine():
    from buraq.conf import settings
    url = settings.DATABASE_URL
    kwargs = dict(echo=settings.DATABASE_ECHO, pool_pre_ping=True)
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = StaticPool
    else:
        kwargs["pool_size"] = getattr(settings, "DATABASE_POOL_SIZE", 10)
        kwargs["max_overflow"] = getattr(settings, "DATABASE_MAX_OVERFLOW", 20)
    return create_async_engine(url, **kwargs)


class _LazyEngine:
    """Lazy proxy — engine is created on first access so settings can be overridden first."""

    _engine = None
    _session_factory = None

    def _init(self):
        if self._engine is None:
            self._engine = _make_engine()
            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

    def __call__(self, *args, **kwargs):
        self._init()
        return self._session_factory(*args, **kwargs)

    def __getattr__(self, name):
        self._init()
        return getattr(self._engine, name)


_lazy = _LazyEngine()
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
