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


class AppConfig:
    """Base class for application configuration."""

    name: str = ""
    verbose_name: str = ""
    label: str = ""

    def __init__(self, app_name: str = "", app_module=None):
        self.app_name = app_name or self.name
        self.label = self.label or self.app_name.rsplit(".", 1)[-1]
        if not self.verbose_name:
            self.verbose_name = self.label.replace("_", " ").title()
        self.module = app_module

    async def ready(self) -> None:
        """Called when the application is fully loaded. Override to connect signals etc."""


class Apps:
    """Registry of installed application configurations."""

    def __init__(self):
        self._apps: dict[str, AppConfig] = {}
        self._ready = False

    def populate(self, installed_apps: list[str]) -> None:
        if self._ready:
            return
        for entry in installed_apps:
            try:
                module_path, class_name = entry.rsplit(".", 1)
                module = importlib.import_module(module_path)
                cls = getattr(module, class_name)
                if isinstance(cls, type) and issubclass(cls, AppConfig):
                    config = cls()
                else:
                    config = AppConfig(entry)
            except (ValueError, ImportError, AttributeError):
                config = AppConfig(entry)
            self._apps[config.label] = config
        self._ready = True

    async def run_ready_hooks(self) -> None:
        for config in self._apps.values():
            await config.ready()

    def get_app_config(self, label: str) -> AppConfig:
        try:
            return self._apps[label]
        except KeyError:
            raise LookupError(f"No installed app with label {label!r}.")

    def get_app_configs(self) -> list[AppConfig]:
        return list(self._apps.values())

    def is_installed(self, app_name: str) -> bool:
        return any(c.app_name == app_name for c in self._apps.values())

    @property
    def ready(self) -> bool:
        return self._ready


apps = Apps()
