"""
Application configuration and registry.

Usage:
    # myapp/apps.py
    from buraq.apps import AppConfig

    class BlogConfig(AppConfig):
        name = "blog"
        verbose_name = "Blog"

        async def ready(self):
            import blog.signals  # connect signals on startup

    # settings.py
    INSTALLED_APPS = ["blog.apps.BlogConfig", "shop"]
"""
from __future__ import annotations

import importlib
import importlib.util


class AppConfig:
    """Base class for application configuration."""

    name: str = ""
    verbose_name: str = ""
    label: str = ""
    #: Marks the config to use when an app module defines more than one.
    default: bool = False

    def __init__(self, app_name: str = "", app_module=None):
        self.app_name = app_name or self.name
        self.label = self.label or self.app_name.rsplit(".", 1)[-1]
        if not self.verbose_name:
            self.verbose_name = self.label.replace("_", " ").title()
        self.module = app_module

    async def ready(self) -> None:
        """Called when the application is fully loaded. Override to connect signals etc."""


def _appconfig_at(dotted_path: str) -> type[AppConfig] | None:
    """Return the ``AppConfig`` subclass named by a dotted path, if it is one."""
    module_path, _, class_name = dotted_path.rpartition(".")
    if not module_path:
        return None
    try:
        module = importlib.import_module(module_path)
    except ImportError:
        return None
    cls = getattr(module, class_name, None)
    if isinstance(cls, type) and issubclass(cls, AppConfig):
        return cls
    return None


def _appconfig_in(app_module: str) -> type[AppConfig] | None:
    """
    Find the ``AppConfig`` declared in ``<app_module>/apps.py``.

    Without this, listing an app by its module path ("blog") instead of its
    config path ("blog.apps.BlogConfig") would silently skip the app's
    ``ready()`` hook -- and ``ready()`` is where receivers get connected, so the
    app would look installed while doing nothing.

    A lone config is used as-is; where there are several, the one setting
    ``default = True`` wins.
    """
    apps_module = f"{app_module}.apps"
    try:
        if importlib.util.find_spec(apps_module) is None:
            return None
    except (ImportError, ValueError):
        return None  # no such app package -- nothing to discover

    # Deliberately outside the guard above: the module exists, so an ImportError
    # raised now is a real fault in it and must not be mistaken for absence.
    module = importlib.import_module(apps_module)

    candidates = [
        obj
        for obj in vars(module).values()
        if isinstance(obj, type)
        and issubclass(obj, AppConfig)
        and obj is not AppConfig
        and obj.__module__ == module.__name__
    ]
    if len(candidates) == 1:
        return candidates[0]
    return next((cls for cls in candidates if cls.default), None)


def _config_for(entry: str) -> AppConfig:
    """
    Build the ``AppConfig`` for one ``INSTALLED_APPS`` entry.

    Accepts either a config path ("blog.apps.BlogConfig") or a plain app module
    ("blog"), and falls back to a bare config so an app with no apps.py still
    registers.
    """
    cls = _appconfig_at(entry) or _appconfig_in(entry)
    return cls() if cls is not None else AppConfig(entry)


class Apps:
    """Registry of installed application configurations."""

    def __init__(self):
        self._apps: dict[str, AppConfig] = {}
        self._ready = False
        self._hooks_ran = False

    def populate(self, installed_apps: list[str]) -> None:
        if self._ready:
            return
        for entry in installed_apps:
            config = _config_for(entry)
            self._apps[config.label] = config
        self._ready = True

    def import_models(self) -> None:
        """
        Import every installed app's ``models`` module.

        A model class only enters the ORM registry when its module executes, so
        anything that walks that registry -- permission creation, autogenerate,
        the admin -- silently sees nothing for an app nobody imported. Entries in
        INSTALLED_APPS may name a config rather than the package, which is why
        this reads the app name off the resolved config instead of the raw entry.
        """
        for config in self._apps.values():
            module = f"{config.app_name}.models"
            try:
                if importlib.util.find_spec(module) is None:
                    continue
            except (ImportError, ValueError):
                continue  # app has no importable package here -- nothing to load
            # Outside the guard: the module exists, so an error raised now is a
            # real fault in it rather than an absence.
            importlib.import_module(module)

    async def run_ready_hooks(self) -> None:
        """Run every app's ``ready()`` exactly once."""
        if self._hooks_ran:
            return
        self._hooks_ran = True
        for config in self._apps.values():
            await config.ready()

    def get_app_config(self, label: str) -> AppConfig:
        try:
            return self._apps[label]
        except KeyError as err:
            raise LookupError(f"No installed app with label {label!r}.") from err

    def get_app_configs(self) -> list[AppConfig]:
        return list(self._apps.values())

    def is_installed(self, app_name: str) -> bool:
        return any(c.app_name == app_name for c in self._apps.values())

    @property
    def ready(self) -> bool:
        return self._ready


apps = Apps()


def configure(settings_module: str | None = None) -> None:
    """
    Prepare Buraq from a synchronous entry point that is not the CLI.

    Alembic's env.py runs in its own process where nothing has loaded the
    project's settings or imported its models, so ``Base.metadata`` is empty and
    autogenerate sees no tables to create -- a freshly scaffolded project could
    never generate its first migration. Loads settings, then every installed
    app's models.

    ``ready()`` hooks are deliberately not run: they are coroutines, and schema
    generation does not need them.
    """
    from buraq.conf import load_settings_module, settings

    load_settings_module(settings_module)
    apps.populate(list(getattr(settings, "INSTALLED_APPS", None) or []))
    apps.import_models()


async def setup() -> None:
    """
    Load ``INSTALLED_APPS`` and run their ``ready()`` hooks.

    ``ready()`` is where an app connects its signal receivers, so anything that
    sends a signal has to have called this first. Idempotent, and the single
    entry point for both the ASGI lifespan and the CLI so the two cannot drift.
    """
    from buraq.conf import settings

    apps.populate(list(getattr(settings, "INSTALLED_APPS", None) or []))
    apps.import_models()
    await apps.run_ready_hooks()
