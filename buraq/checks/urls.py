"""Checks that the project's own modules import — registered automatically."""
from __future__ import annotations

import importlib

from buraq.checks.registry import Error, registry


@registry.register
def check_root_urlconf_imports(settings, **kwargs):
    """The URLconf has to import before anything can be routed.

    `buraq check` is what you run to find problems before starting the server,
    and it reported a clean project while `runserver` failed on the first line
    of config/urls.py -- a missing third-party package, a typo in an import, a
    view that was renamed. Those are the likeliest ways a project breaks, and
    the one command meant to catch them did not look.
    """
    dotted = getattr(settings, "ROOT_URLCONF", None)
    if not dotted:
        return []
    try:
        importlib.import_module(dotted)
    except ImportError as exc:
        return [Error(
            f"ROOT_URLCONF is {dotted!r}, which could not be imported: {exc}",
            hint="Check the imports at the top of that file, and that every "
                 "package it uses is installed in this environment.",
            id="urls.E001",
        )]
    except Exception as exc:
        # Anything else raised while importing is still a project that will not
        # start, and saying which module and what happened beats a traceback
        # from runserver a minute later.
        return [Error(
            f"ROOT_URLCONF is {dotted!r}, which raised "
            f"{type(exc).__name__} on import: {exc}",
            hint="Run the module directly to see the full traceback.",
            id="urls.E002",
        )]
    return []
