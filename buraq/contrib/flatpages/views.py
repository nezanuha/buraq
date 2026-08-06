"""View that serves FlatPage objects by URL path."""
from __future__ import annotations

from starlette.requests import Request
from starlette.responses import HTMLResponse

from buraq.contrib.flatpages.models import FlatPage
from buraq.exceptions import Http404


async def flatpage(request: Request) -> HTMLResponse:
    url = request.path_params.get("url", request.url.path)
    if not url.startswith("/"):
        url = "/" + url

    page = await FlatPage.objects.get_or_none(url=url)
    if page is None:
        raise Http404(f"No flatpage found matching URL {url!r}.")

    template_name = page.template_name or "flatpages/default.html"
    try:
        from buraq.core.templating import templates
        return templates.TemplateResponse(request, template_name, {"flatpage": page})
    except Exception:
        return HTMLResponse(page.content)
