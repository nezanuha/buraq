"""
Vary-header decorators.

Grouped by concern, so Vary-header decorators have a predictable home::

    from buraq.views.decorators.vary import vary_on_headers

    @vary_on_headers("Accept-Language")
    async def home(request):
        ...
"""

from buraq.decorators import vary_on_cookie, vary_on_headers

__all__ = ["vary_on_headers", "vary_on_cookie"]
