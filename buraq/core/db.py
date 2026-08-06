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
    kwargs = dict(echo=settings.DEBUG, pool_pre_ping=True)
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = StaticPool
    else:
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
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


async def create_tables() -> None:
    _lazy._init()
    async with _lazy._engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
