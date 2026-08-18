"""
HTTP method and conditional-request decorators.

Grouped by concern, so HTTP-method decorators have a predictable home::

    from buraq.views.decorators.http import require_POST

    @require_POST
    async def submit(request):
        ...
"""

from buraq.decorators import (
    condition,
    require_GET,
    require_http_methods,
    require_POST,
    require_safe,
)

__all__ = ["require_GET", "require_POST", "require_http_methods", "require_safe", "condition"]
