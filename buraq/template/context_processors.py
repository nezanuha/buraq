"""
Context processors — callables that inject data into every template context.

Configure in settings:
    TEMPLATE_CONTEXT_PROCESSORS = [
        "buraq.template.context_processors.request",
        "buraq.template.context_processors.auth",
        "buraq.template.context_processors.debug",
        "buraq.template.context_processors.i18n",
    ]

Each processor receives the current request and returns a dict merged into
the template context before rendering. Use run_context_processors() in views
or TemplateResponse to apply them automatically.
"""
from __future__ import annotations

import importlib
import inspect


def request(req) -> dict:
    """Adds the current request object to the template context."""
    return {"request": req}


def auth(req) -> dict:
    """Adds the authenticated user to the template context."""
    return {"user": getattr(req, "user", None)}


def debug(req) -> dict:
    """Adds DEBUG flag — only when DEBUG=True, so it's never exposed in production."""
    from buraq.conf import settings
    return {"DEBUG": settings.DEBUG} if settings.DEBUG else {}


def i18n(req) -> dict:
    """Adds current language code to the template context."""
    from buraq.conf import settings
    lang = getattr(getattr(req, "state", None), "language", None) or settings.LANGUAGE_CODE
    return {"LANGUAGE_CODE": lang}


def _processor_paths() -> list[str]:
    """Configured processor import paths, falling back to the defaults."""
    from buraq.conf import settings

    return getattr(
        settings,
        "TEMPLATE_CONTEXT_PROCESSORS",
        [
            "buraq.template.context_processors.request",
            "buraq.template.context_processors.auth",
        ],
    )


def _load(path: str):
    module_path, func_name = path.rsplit(".", 1)
    return getattr(importlib.import_module(module_path), func_name)


async def run_context_processors(req) -> dict:
    """
    Run every configured ``TEMPLATE_CONTEXT_PROCESSORS`` entry and merge the
    results into one context dict.

    Awaited by the ``render()`` shortcut. Processors may be sync or async --
    async ones are awaited, which is what lets a processor query the database
    (every query in Buraq is async).
    """
    context: dict = {}
    for path in _processor_paths():
        result = _load(path)(req)
        if inspect.isawaitable(result):
            result = await result
        context.update(result)
    return context
