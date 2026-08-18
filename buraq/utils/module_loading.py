"""
Module loading utilities — import_string, autodiscover_modules.

Usage:
    from buraq.utils.module_loading import import_string, autodiscover_modules

    Backend = import_string("buraq.contrib.cache.backends.redis.RedisCacheBackend")
    autodiscover_modules("signals")   # imports <app>.signals for each INSTALLED_APP
"""
from __future__ import annotations

import importlib
import logging

_log = logging.getLogger(__name__)


def import_string(dotted_path: str):
    """
    Import a module, class, or function by its dotted Python path.

    Works for top-level modules (e.g. ``"json"``), submodules
    (``"os.path"``), and attributes (``"myapp.backends.MyBackend"``).

    Usage:
        cls = import_string("myapp.backends.MyBackend")
        mod = import_string("os.path")
        obj = cls()
    """
    try:
        return importlib.import_module(dotted_path)
    except ImportError:
        pass

    try:
        module_path, attr_name = dotted_path.rsplit(".", 1)
    except ValueError as exc:
        raise ImportError(f"{dotted_path!r} is not a valid dotted path") from exc

    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ImportError(
            f"Could not import module {module_path!r}: {exc}"
        ) from exc

    try:
        return getattr(module, attr_name)
    except AttributeError:
        # attr_name might itself be a submodule
        try:
            return importlib.import_module(dotted_path)
        except ImportError as exc:
            raise ImportError(
                f"Module {module_path!r} does not define {attr_name!r}"
            ) from exc


def autodiscover_modules(*module_names: str, register_to=None) -> None:
    """
    Auto-import ``<app>.<module_name>`` for every app in INSTALLED_APPS.

    Imports a named submodule from every installed app — useful for signals,
    admin registrations, management commands, or any side-effect-driven imports.

    Usage:
        autodiscover_modules("signals")       # imports myapp.signals for each app
        autodiscover_modules("admin", "tasks")
    """
    from buraq.conf import settings

    for app_name in settings.INSTALLED_APPS:
        for module_name in module_names:
            full = f"{app_name}.{module_name}"
            try:
                importlib.import_module(full)
                _log.debug("autodiscover: loaded %s", full)
            except ModuleNotFoundError:
                pass
            except Exception:
                _log.exception("autodiscover: error loading %s", full)
