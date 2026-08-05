"""
Language-switching view for URL-prefix-based i18n.

Wire it up in urls.py:
    from buraq.contrib.i18n.views import set_language
    urlpatterns = [
        path("/i18n/set_language", set_language),
        ...
    ]

Then POST (or GET) to /i18n/set_language?language=ar&next=/about
→ redirects to /ar/about
"""
from __future__ import annotations

from fastapi.responses import RedirectResponse
from starlette.requests import Request

from buraq.utils.translation import check_for_language, translate_url


async def set_language(request: Request) -> RedirectResponse:
    """
    Switch the active language by redirecting to the language-prefixed URL.

    Reads ``language`` from POST body or query string.
    Reads ``next`` from POST body, query string, or Referer header.
    """
    if request.method == "POST":
        form = await request.form()
        language = str(form.get("language", ""))
        next_url = str(form.get("next", ""))
    else:
        language = request.query_params.get("language", "")
        next_url = request.query_params.get("next", "")

    # Fall back to Referer, then root
    if not next_url:
        referer = request.headers.get("referer", "/")
        # Extract path only from full Referer URL
        from urllib.parse import urlparse
        next_url = urlparse(referer).path or "/"

    if len(language) > 500 or not check_for_language(language):
        return RedirectResponse(next_url, status_code=302)

    redirect_to = translate_url(next_url, language)
    return RedirectResponse(redirect_to, status_code=302)
