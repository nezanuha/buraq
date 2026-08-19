"""Settings access, and loading the project's settings module."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from buraq.conf.defaults import BuraqSettings, settings

__all__ = ["BuraqSettings", "settings", "discover_settings_module", "load_settings_module"]


def discover_settings_module() -> str | None:
    """
    Locate the project's settings module when one was not named explicitly.

    Settings declared in Python rather than in .env -- INSTALLED_APPS,
    TEMPLATES_DIR and friends -- are invisible to the environment-based loading
    that backs ``settings``. Without this, a process that nobody configured runs
    with an empty INSTALLED_APPS.

    Checks the two conventional layouts, then any single top-level package
    holding a settings.py. Ambiguity yields nothing rather than a wrong guess.
    """
    cwd = Path.cwd()
    if (cwd / "config" / "settings.py").is_file():
        return "config.settings"
    if (cwd / "settings.py").is_file():
        return "settings"
    found = [
        path
        for path in cwd.glob("*/settings.py")
        if not path.parent.name.startswith(".")
        and (path.parent / "__init__.py").is_file()
    ]
    return f"{found[0].parent.name}.settings" if len(found) == 1 else None


def load_settings_module(name: str | None = None) -> str | None:
    """
    Import the project's settings module and apply it to ``settings``.

    Returns the module name that was loaded, or None when there was nothing to
    load. Explicit name wins, then BURAQ_SETTINGS_MODULE, then discovery.
    """
    name = name or os.environ.get("BURAQ_SETTINGS_MODULE") or discover_settings_module()
    if not name:
        return None

    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    module = importlib.import_module(name)
    for key, value in vars(module).items():
        if key.isupper() and not key.startswith("_") and hasattr(settings, key):
            setattr(settings, key, value)
    return name
