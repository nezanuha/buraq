import importlib
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from buraq.conf import settings

_log = logging.getLogger(__name__)
_templates: Jinja2Templates | None = None


def _collect_template_dirs() -> list[str]:
    """
    Return all template directories in priority order:
    1. Project-level TEMPLATES_DIR (if set)
    2. APP_DIRS — each installed app's ``templates/`` subfolder
    """
    dirs: list[str] = []

    project_dir = settings.TEMPLATES_DIR or str(Path.cwd() / "templates")
    if Path(project_dir).is_dir():
        dirs.append(project_dir)

    if getattr(settings, "APP_DIRS", True):
        for app_name in getattr(settings, "INSTALLED_APPS", []):
            try:
                mod = importlib.import_module(app_name)
                app_path = Path(mod.__file__).parent if mod.__file__ else None
                if app_path:
                    tmpl_path = app_path / "templates"
                    if tmpl_path.is_dir():
                        dirs.append(str(tmpl_path))
            except (ImportError, AttributeError):
                pass

    if not dirs:
        dirs.append(project_dir)

    return dirs


def get_templates() -> Jinja2Templates:
    global _templates
    if _templates is None:
        template_dirs = _collect_template_dirs()
        _templates = Jinja2Templates(directory=template_dirs)
        _templates.env.auto_reload = settings.DEBUG

        # ── Built-in globals ───────────────────────────────────────────────

        # Messages
        from buraq.contrib.messages import get_messages
        _templates.env.globals["get_messages"] = get_messages

        # URL reversal
        from buraq.urls import reverse
        _templates.env.globals["url"] = reverse

        # Static files — route through storage so ManifestStorage returns hashed URLs
        def _static(path: str) -> str:
            try:
                from buraq.contrib.staticfiles.storage import get_storage
                return get_storage().url(path)
            except Exception:
                return settings.STATIC_URL.rstrip("/") + "/" + path.lstrip("/")

        def _media(path: str) -> str:
            return settings.MEDIA_URL.rstrip("/") + "/" + path.lstrip("/")

        _templates.env.globals["static"] = _static
        _templates.env.globals["media"] = _media
        _templates.env.globals["STATIC_URL"] = settings.STATIC_URL
        _templates.env.globals["MEDIA_URL"] = settings.MEDIA_URL

        # Django-style {% static %} / {% media %} block tags
        from buraq.contrib.staticfiles.templatetags import StaticExtension
        _templates.env.add_extension(StaticExtension)

        # Template fragment caching — {% cache 300 "key" %}...{% endcache %}
        from buraq.template.cache import CacheExtension
        _templates.env.add_extension(CacheExtension)

        # CSRF
        from buraq.contrib.csrf import get_token as _get_csrf_token

        def _csrf_token_func(request=None):
            """Return the raw CSRF token string."""
            return _get_csrf_token(request) if request else ""

        def _csrf_input(request=None):
            """Return a hidden <input> field with the CSRF token."""
            from markupsafe import Markup
            token = _get_csrf_token(request) if request else ""
            return Markup(f'<input type="hidden" name="csrfmiddlewaretoken" value="{token}">')

        _templates.env.globals["csrf_token"] = _csrf_token_func
        _templates.env.globals["csrf_input"] = _csrf_input

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

        # ── Built-in filters (Django-compatible) ───────────────────────────
        from buraq.template.builtins import register_builtins
        register_builtins(_templates.env)

        # ── App templatetags ───────────────────────────────────────────────
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


