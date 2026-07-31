"""
Django-style shortcuts for Buraq views.

from buraq.shortcuts import render, redirect, get_object_or_404
"""
from typing import Any

from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse


def render(request: Request, template_name: str, context: dict | None = None) -> HTMLResponse:
    """
    Render a Jinja2 template and return an HTMLResponse — exactly like Django's render().

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
    Return an HTTP redirect — like Django's redirect().

    Usage:
        return redirect('/posts/')
        return redirect('post_list')   # redirect by route name (needs app reference)
        return redirect('/posts/', permanent=True)
    """
    return RedirectResponse(url=to, status_code=301 if permanent else 302)


async def get_object_or_404(model: Any, **kwargs) -> Any:
    """
    Fetch a single object or raise 404 — exactly like Django's get_object_or_404().

    Usage:
        post = await get_object_or_404(Post, id=id)
        post = await get_object_or_404(Post, slug=slug)
    """
    obj = await model.objects.get_or_none(**kwargs)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} not found")
    return obj
