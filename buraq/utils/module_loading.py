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
    Import a class or function by its dotted Python path.

    Usage:
        cls = import_string("myapp.backends.MyBackend")
        obj = cls()
    """
    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
    except ValueError as exc:
        raise ImportError(f"{dotted_path!r} is not a valid dotted path") from exc
    module = importlib.import_module(module_path)
    try:
        return getattr(module, class_name)
    except AttributeError as exc:
        raise ImportError(
            f"Module {module_path!r} does not define {class_name!r}"
        ) from exc


def autodiscover_modules(*module_names: str, register_to=None) -> None:
    """
    Auto-import ``<app>.<module_name>`` for every app in INSTALLED_APPS.

    Works like Django's autodiscover — useful for signals, admin registrations,
    management commands, or any side-effect-driven imports.

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
