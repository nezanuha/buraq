import importlib
import logging
from pathlib import Path

from fastapi.templating import Jinja2Templates

from buraq.conf import settings
from buraq.exceptions import ImproperlyConfigured

_log = logging.getLogger(__name__)
_templates: Jinja2Templates | None = None


def _collect_template_dirs() -> list[str]:
    """
    Return all template directories in priority order:
    1. Project-level TEMPLATES_DIR (if set)
    2. APP_DIRS — each installed app's ``templates/`` subfolder

    TEMPLATES_DIR takes one path or several. A project with a shared theme
    beside its own templates has two roots, and a single string could only ever
    name one of them.
    """
    dirs: list[str] = []

    configured = settings.TEMPLATES_DIR or str(Path.cwd() / "templates")
    project_dirs = [configured] if isinstance(configured, (str, Path)) else list(configured)
    for project_dir in project_dirs:
        if Path(project_dir).is_dir():
            dirs.append(str(project_dir))

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


def _import_dotted(path: str, setting: str):
    """Resolve ``"jinja2.StrictUndefined"`` to the class it names."""
    import importlib

    module_path, _, name = path.rpartition(".")
    try:
        return getattr(importlib.import_module(module_path), name)
    except (ImportError, AttributeError, ValueError) as exc:
        raise ImproperlyConfigured(
            f"TEMPLATE_OPTIONS[{setting!r}] is {path!r}, "
            f"which could not be imported: {exc}"
        ) from exc


def _build_env(template_dirs: list[str]):
    """
    The Jinja environment, with anything TEMPLATE_OPTIONS asks for.

    Starlette builds a default environment and offers no way to alter it, so
    ``undefined``, ``trim_blocks`` and the extension list were unreachable: a
    typo in a template rendered as empty text rather than raising, and a project
    could not add ``jinja2.ext.loopcontrols`` or its own extension. Building the
    environment here makes every Jinja option a setting.
    """
    import jinja2

    options = dict(getattr(settings, "TEMPLATE_OPTIONS", None) or {})
    extensions = options.pop("extensions", None) or []

    # `undefined` and `finalize` are a class and a callable, but a settings file
    # should not have to import jinja2 to name them -- every other setting here
    # takes a dotted path. Options that are legitimately strings, like
    # block_start_string, are left alone.
    for key in ("undefined", "finalize", "bytecode_cache"):
        if isinstance(options.get(key), str):
            options[key] = _import_dotted(options[key], key)

    options.setdefault("loader", jinja2.FileSystemLoader(template_dirs))
    # Starlette's default, and the one that matters: without it every variable
    # interpolated into a page is a cross-site scripting hole.
    options.setdefault("autoescape", jinja2.select_autoescape())

    env = jinja2.Environment(**options)
    for extension in extensions:
        env.add_extension(extension)
    return env


def get_templates() -> Jinja2Templates:
    global _templates
    if _templates is None:
        template_dirs = _collect_template_dirs()
        _templates = Jinja2Templates(env=_build_env(template_dirs))
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

        # {% static %} / {% media %} block tags
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

        # ── Built-in filters ───────────────────────────────────────────────
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


