"""
Shortcuts for Buraq views — render, redirect, get_object_or_404, render_to_string.

from buraq.shortcuts import render, redirect, get_object_or_404, render_to_string
"""
from typing import Any

from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse


def render(request: Request, template_name: str, context: dict | None = None) -> HTMLResponse:
    """
    Render a Jinja2 template and return an HTMLResponse.

    Usage:
        async def post_list(request):
            posts = await Post.objects.all()
            return render(request, 'posts/post_list.html', {'posts': posts})
    """
    from buraq.core.templating import get_templates
    return get_templates().TemplateResponse(
        request,
        template_name,
        context or {},
    )


def redirect(to: str, permanent: bool = False) -> RedirectResponse:
    """
    Return an HTTP redirect response.

    Usage:
        return redirect('/posts/')
        return redirect('post_list')   # redirect by route name (needs app reference)
        return redirect('/posts/', permanent=True)
    """
    return RedirectResponse(url=to, status_code=301 if permanent else 302)


def render_to_string(
    template_name: str | list[str],
    context: dict | None = None,
    request: Request | None = None,
) -> str:
    """
    Render a template to a string.

    Useful for rendering email bodies, partial HTML, or any template outside of a view::

        body = render_to_string("emails/welcome.html", {"user": user})
        html = render_to_string(["partials/card.html", "partials/default.html"], context)
    """
    from buraq.template.loader import render_to_string as _render
    return _render(template_name, context, request)


async def get_object_or_404(model: Any, **kwargs) -> Any:
    """
    Fetch a single object or raise 404.

    Usage:
        post = await get_object_or_404(Post, id=id)
        post = await get_object_or_404(Post, slug=slug)
    """
    obj = await model.objects.get_or_none(**kwargs)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return obj
