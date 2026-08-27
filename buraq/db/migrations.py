"""The Alembic environment, so a project's ``alembic/env.py`` can be two lines.

Every line of the env.py the scaffold used to write was framework plumbing:
loading settings, importing models so ``Base.metadata`` is populated, skipping
the tables migrations do not own, and opening an async connection. None of it
varied between projects — a generated env.py contained no reference to the
project that owned it — so it lives here and the scaffold writes a call to
``run()`` instead.

An existing project's longhand env.py keeps working; this is where new ones
point, not a change to how migrations run.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import Any

from alembic.config import Config
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

#: Set by ``buraq makemigrations`` to scope one autogenerate run to one app, so
#: the migration it writes lands in that app's directory and describes only its
#: own tables. Unset means the whole project, which is what ``migrate`` wants.
_APP_ENV_VAR = "BURAQ_MIGRATIONS_APP"


def _include_object(
    obj: Any, name: str, type_: str, reflected: bool, compare_to: Any
) -> bool:
    """Keep autogenerate away from tables this run does not own."""
    import os

    from buraq.core.db import app_table_names, tables_migrations_ignore

    if type_ != "table":
        return True
    if name in tables_migrations_ignore():
        return False

    app = os.environ.get(_APP_ENV_VAR)
    if app:
        # Every other app's tables are somebody else's migration. Excluding them
        # rather than ignoring the run keeps autogenerate from proposing a drop
        # for a table it simply is not looking at this time.
        return name in app_table_names(app)
    return True


def _do_run_migrations(connection: Connection) -> None:
    # Read Base.metadata here rather than at import time: model modules
    # register their tables on it during configure(), which runs later.
    from buraq.core.db import Base

    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    from buraq.conf import settings

    config = context.config
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.DATABASE_URL
    connectable = async_engine_from_config(
        configuration, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


def run() -> None:
    """Run migrations for the project whose alembic.ini invoked this.

    Called from a project's ``alembic/env.py``::

        from buraq.db.migrations import run

        run()

    Loads settings and imports every installed app's models before anything
    else — without that ``Base.metadata`` is empty, autogenerate sees no
    tables, and a new project can never generate its first migration.
    """
    from buraq.apps import configure

    configure()

    config = context.config
    if config.config_file_name is not None:
        fileConfig(config.config_file_name)

    if context.is_offline_mode():
        return

    asyncio.run(_run_async())


def version_locations() -> list[str]:
    """
    Where Alembic should look for migrations, derived from INSTALLED_APPS.

    Every app that has a migrations package contributes one entry, written as
    ``<app>:migrations`` so it resolves against the installed package whether it
    is one of Buraq's or one of the project's. Deriving it here rather than
    reading it from a config file means adding an app to INSTALLED_APPS is the
    only step -- there is nothing to keep in sync.
    """
    import importlib.util

    from buraq.conf import settings

    locations = []
    for app in getattr(settings, "INSTALLED_APPS", None) or []:
        try:
            spec = importlib.util.find_spec(f"{app}.migrations")
        except (ImportError, ValueError):
            continue
        if spec is not None:
            locations.append(f"{app}:migrations")
    return locations


def config(database_url: str | None = None) -> Config:
    """
    The Alembic configuration for the project in the working directory.

    Built in memory rather than read from an alembic.ini. Every value that file
    held is already known: the database comes from settings, and the version
    locations from INSTALLED_APPS. A file restating them is one more thing to
    keep correct, and it went stale the moment an app was added.
    """
    from buraq.conf import settings

    cfg = Config()
    cfg.set_main_option("script_location", "buraq.db:alembic")
    # The project directory itself, so its own apps are importable as packages.
    cfg.set_main_option("prepend_sys_path", ".")
    # One path per line: "os" would make the separator differ between Windows
    # and Linux, and newline survives paths that contain spaces.
    cfg.set_main_option("path_separator", "newline")
    cfg.set_main_option("version_locations", "\n".join(version_locations()))
    cfg.set_main_option(
        "sqlalchemy.url", database_url or getattr(settings, "DATABASE_URL", "")
    )
    return cfg
