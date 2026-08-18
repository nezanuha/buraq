"""
CSRF decorators.

Grouped by concern, so CSRF decorators have a predictable home::

    from buraq.views.decorators.csrf import csrf_exempt

    @csrf_exempt
    async def webhook(request):
        ...

CSRF protection in Buraq is opt-in per view (or via ``CsrfViewMiddleware``), so
``csrf_protect`` and ``ensure_csrf_cookie`` come from :mod:`buraq.contrib.csrf`.
"""

from buraq.contrib.csrf import csrf_protect, ensure_csrf_cookie
from buraq.decorators import csrf_exempt

__all__ = ["csrf_exempt", "csrf_protect", "ensure_csrf_cookie"]
