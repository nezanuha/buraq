import importlib
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from buraq.conf import settings

_log = logging.getLogger(__name__)
_templates: Jinja2Templates | None = None


def get_templates() -> Jinja2Templates:
    global _templates
    if _templates is None:
        templates_dir = settings.TEMPLATES_DIR or str(Path.cwd() / "templates")
        _templates = Jinja2Templates(directory=templates_dir)
        _templates.env.auto_reload = settings.DEBUG

        # Built-in globals
        from buraq.contrib.messages import get_messages
        _templates.env.globals["get_messages"] = get_messages

        # i18n globals
        if settings.USE_I18N:
            from buraq.utils.translation import (
                get_language,
                get_language_bidi,
                gettext,
                ngettext,
                pgettext,
            )
            _templates.env.globals["_"]               = gettext
            _templates.env.globals["gettext"]         = gettext
            _templates.env.globals["ngettext"]        = ngettext
            _templates.env.globals["pgettext"]        = pgettext
            _templates.env.globals["get_language"]    = get_language
            _templates.env.globals["get_language_bidi"] = get_language_bidi

        # Apply all @register.global / @register.filter / @register.test
        # collected from INSTALLED_APPS templatetags.py files
        from buraq.template.registry import _registry
        _registry.apply(_templates.env)

    return _templates


def discover_templatetags() -> None:
    """
    Import ``templatetags.py`` from every app in ``INSTALLED_APPS``.

    Each file's ``@register.global``, ``@register.filter``, and
    ``@register.test`` decorators populate the shared ``_registry``.
    This is called once at startup before ``get_templates()`` so that
    all tags are available when the first template is rendered.
    """
    for app_name in settings.INSTALLED_APPS:
        module_path = f"{app_name}.templatetags"
        try:
            importlib.import_module(module_path)
            _log.debug("Loaded templatetags from %s", module_path)
        except ModuleNotFoundError:
            pass
        except Exception:
            _log.exception("Error loading templatetags from %s", module_path)


def register_static(app: FastAPI) -> None:
    static_dir = settings.STATIC_DIR or str(Path.cwd() / "static")
    if Path(static_dir).exists():
        app.mount(settings.STATIC_URL.rstrip("/"), StaticFiles(directory=static_dir), name="static")

    if settings.MEDIA_DIR and Path(settings.MEDIA_DIR).exists():
        app.mount(
            settings.MEDIA_URL.rstrip("/"),
            StaticFiles(directory=settings.MEDIA_DIR),
            name="media",
        )
