"""
Template loader utilities — render_to_string, get_template, select_template.

Usage:
    from buraq.template.loader import render_to_string, get_template, select_template
"""
from __future__ import annotations

from typing import Any


class TemplateDoesNotExist(Exception):
    pass


def get_template(template_name: str):
    """
    Load and return a Jinja2 template by name.

    Raises ``TemplateDoesNotExist`` if the template cannot be found.

    Usage::

        template = get_template("emails/welcome.html")
        html = template.render({"user": user})
    """
    from jinja2 import TemplateNotFound

    from buraq.core.templating import get_templates

    try:
        return get_templates().env.get_template(template_name)
    except TemplateNotFound as exc:
        raise TemplateDoesNotExist(template_name) from exc


def select_template(template_name_list: list[str]):
    """
    Try each template name in order and return the first one that exists.

    Raises ``TemplateDoesNotExist`` if none are found.

    Usage::

        template = select_template([
            f"posts/{post.type}.html",
            "posts/default.html",
        ])
    """
    from jinja2 import TemplateNotFound

    from buraq.core.templating import get_templates

    env = get_templates().env
    for name in template_name_list:
        try:
            return env.get_template(name)
        except TemplateNotFound:
            continue

    raise TemplateDoesNotExist(", ".join(template_name_list))


def render_to_string(
    template_name: str | list[str],
    context: dict[str, Any] | None = None,
    request: Any = None,
) -> str:
    """
    Render a template to a string.

    Accepts a single template name or a list (tries each in order).
    Optionally accepts a ``request`` to inject it into the template context.

    Usage::

        # In a view — render email body
        body = render_to_string("emails/welcome.html", {"user": user})

        # Pass the request for access to request.user, etc.
        html = render_to_string("partials/nav.html", {}, request=request)

        # Try multiple templates
        html = render_to_string(["widgets/custom.html", "widgets/default.html"], context)
    """
    if isinstance(template_name, (list, tuple)):
        template = select_template(list(template_name))
    else:
        template = get_template(template_name)

    ctx: dict[str, Any] = dict(context or {})
    if request is not None:
        ctx.setdefault("request", request)

    return template.render(ctx)
