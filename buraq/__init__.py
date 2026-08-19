"""Buraq — the async Python framework."""


def _bootstrap_cli() -> None:
    """
    Re-execute the `buraq` command using the current project's virtualenv.

    The console script lives inside whichever environment Buraq was installed
    into. Installed globally (so `buraq startproject` works anywhere), it would
    otherwise run a project's commands against that global environment rather
    than the project's own — silently using the wrong dependency set.

    Runs before the rest of the package is imported, because importing Buraq
    validates settings; the swap has to happen first. Only fires for the
    console script, so `import buraq` in application code is unaffected.
    Set BURAQ_NO_BOOTSTRAP=1 to disable.
    """
    import os
    import sys
    from pathlib import Path

    if os.environ.get('BURAQ_NO_BOOTSTRAP'):
        return
    if Path(sys.argv[0]).stem != 'buraq':
        return

    venv = Path.cwd() / '.venv'
    python = venv / 'Scripts' / 'python.exe'
    if not python.exists():
        python = venv / 'bin' / 'python'
    if not python.exists():
        return

    try:
        same = Path(sys.executable).resolve() == python.resolve()
    except OSError:
        return
    if same:
        return

    os.environ['BURAQ_NO_BOOTSTRAP'] = '1'   # guard against exec loops
    argv = [str(python), '-m', 'buraq.management.cli', *sys.argv[1:]]

    if os.name == 'nt':
        # Windows has no real exec: os.execv() spawns a new process and exits
        # this one, so the shell sees the command finish and returns the prompt
        # while the server keeps running detached -- Ctrl+C then reaches nobody.
        # Staying alive as a thin parent keeps the console attached and signals
        # working, at the cost of one extra process.
        import subprocess

        raise SystemExit(subprocess.run(argv).returncode)

    os.execv(str(python), argv)


_bootstrap_cli()

# Imports deliberately follow _bootstrap_cli(): the interpreter swap must
# happen before importing anything that validates settings.
from buraq import db, forms, models, views  # noqa: E402
from buraq.core.application import Buraq  # noqa: E402
from buraq.core.db import Base, get_db  # noqa: E402
from buraq.core.routing import Router  # noqa: E402
from buraq.orm.aggregates import Avg, Count, Max, Min, Sum  # noqa: E402
from buraq.orm.query import F, Q  # noqa: E402
from buraq.shortcuts import get_object_or_404, redirect, render  # noqa: E402
from buraq.urls import delete, get, include, patch, path, post, put  # noqa: E402

try:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _version

    __version__ = _version('buraq')
except PackageNotFoundError:  # running from a source checkout
    __version__ = '0.0.0+unknown'

__all__ = [
    # App
    "Buraq", "Router", "Base", "get_db",
    # URL routing
    "path", "get", "post", "put", "patch", "delete", "include",
    # Shortcuts
    "render", "redirect", "get_object_or_404",
    # ORM
    "models", "Q", "F", "Count", "Sum", "Avg", "Min", "Max",
    # Views & Forms
    "views", "forms",
    # DB
    "db",
]
