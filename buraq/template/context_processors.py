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


async def run_context_processors(req) -> dict:
    """
    Run all configured TEMPLATE_CONTEXT_PROCESSORS and merge their results.

    Called automatically by TemplateResponse before rendering.
    """
    from buraq.conf import settings
    processors = getattr(settings, "TEMPLATE_CONTEXT_PROCESSORS", [
        "buraq.template.context_processors.request",
        "buraq.template.context_processors.auth",
    ])
    context: dict = {}
    for path in processors:
        module_path, func_name = path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        fn = getattr(module, func_name)
        result = fn(req)
        if inspect.isawaitable(result):
            result = await result
        context.update(result)
    return context
