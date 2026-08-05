"""
Auth mixins for class-based views.

Usage:
    from buraq.views.mixins import LoginRequiredMixin, PermissionRequiredMixin

    class MyView(LoginRequiredMixin, DetailView):
        model = Post

    class AdminView(PermissionRequiredMixin, DetailView):
        model = Post
        permission_required = "blog.change_post"
"""
from __future__ import annotations

from starlette.responses import RedirectResponse


class AccessMixin:
    """Base mixin that handles redirecting unauthenticated or unauthorized users."""

    login_url: str = "/accounts/login/"
    raise_exception: bool = False

    def get_login_url(self) -> str:
        return self.login_url

    async def handle_no_permission(self, request):
        if self.raise_exception:
            from starlette.responses import Response
            return Response("Forbidden", status_code=403)
        return RedirectResponse(self.get_login_url(), status_code=302)


class LoginRequiredMixin(AccessMixin):
    """Redirect unauthenticated users to the login page."""

    async def dispatch(self, request, **kwargs):
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return await self.handle_no_permission(request)
        return await super().dispatch(request, **kwargs)


class UserPassesTestMixin(AccessMixin):
    """
    Deny access if ``test_func()`` returns False.

    Override ``test_func`` in your view:

        class MyView(UserPassesTestMixin, View):
            async def test_func(self, request):
                return request.user.is_staff
    """

    async def test_func(self, request) -> bool:
        return True

    async def dispatch(self, request, **kwargs):
        if not await self.test_func(request):
            return await self.handle_no_permission(request)
        return await super().dispatch(request, **kwargs)


class PermissionRequiredMixin(LoginRequiredMixin):
    """
    Require the user to have a specific permission.

        class MyView(PermissionRequiredMixin, DetailView):
            model = Post
            permission_required = "blog.change_post"
            # or multiple:
            permission_required = ["blog.change_post", "blog.view_post"]
    """

    permission_required: str | list[str] = ""

    def get_permission_required(self) -> list[str]:
        if isinstance(self.permission_required, str):
            return [self.permission_required] if self.permission_required else []
        return list(self.permission_required)

    async def has_permission(self, request) -> bool:
        user = getattr(request, "user", None)
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        perms = self.get_permission_required()
        if not perms:
            return True
        for perm in perms:
            if not await user.has_perm(perm):
                return False
        return True

    async def dispatch(self, request, **kwargs):
        if not await self.has_permission(request):
            return await self.handle_no_permission(request)
        # Skip LoginRequiredMixin dispatch (already checked)
        from buraq.views.base import View
        return await View.dispatch(self, request, **kwargs)


__all__ = ["AccessMixin", "LoginRequiredMixin", "UserPassesTestMixin", "PermissionRequiredMixin"]
