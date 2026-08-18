"""
Authentication and authorisation decorators.

Grouped by concern, so auth decorators have a predictable home::

    from buraq.contrib.auth.decorators import login_required, permission_required

    @login_required
    async def dashboard(request):
        ...

The implementations live in :mod:`buraq.decorators`, which also re-exports the
HTTP, cache, CSRF and vary decorators in one place. Both import paths return the
same objects — use whichever reads better in your project.
"""

from buraq.decorators import (
    login_required,
    permission_required,
    staff_required,
    superuser_required,
    user_passes_test,
)

__all__ = [
    "login_required",
    "permission_required",
    "user_passes_test",
    # Buraq-specific shorthands
    "staff_required",
    "superuser_required",
]
