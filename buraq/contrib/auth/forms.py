"""
Authentication forms.

Usage::

    from buraq.contrib.auth.forms import AuthenticationForm, PasswordChangeForm

    async def login_view(request):
        form = AuthenticationForm(await request.form())
        if form.is_valid():
            user = await form.get_user(request)
            if user:
                await login(request, user)
                return redirect("/")
        return render(request, "auth/login.html", {"form": form})
"""
from __future__ import annotations

from buraq.exceptions import ValidationError


class _BaseForm:
    def __init__(self, data: dict | None = None):
        self.data = data or {}
        self._errors: dict[str, list[str]] = {}

    def is_valid(self) -> bool:
        self._errors = {}
        self._clean()
        return not self._errors

    def _clean(self) -> None:
        pass

    def add_error(self, field: str, message: str) -> None:
        self._errors.setdefault(field, []).append(message)

    @property
    def errors(self) -> dict[str, list[str]]:
        return self._errors


class AuthenticationForm(_BaseForm):
    """
    Form for authenticating a user with username and password.

    Usage::

        form = AuthenticationForm(await request.form())
        if form.is_valid():
            user = await form.get_user(request)
    """

    def _clean(self) -> None:
        if not self.data.get("username"):
            self.add_error("username", "This field is required.")
        if not self.data.get("password"):
            self.add_error("password", "This field is required.")

    async def get_user(self, request):
        from buraq.contrib.auth import authenticate
        return await authenticate(
            request,
            username=self.data.get("username", ""),
            password=self.data.get("password", ""),
        )


class BaseUserCreationForm(_BaseForm):
    """
    Form for creating a new user. Validates that the two password fields match.
    Subclass and override ``save()`` to persist the new user.

    Usage::

        form = BaseUserCreationForm(await request.form())
        if form.is_valid():
            await form.save()
    """

    def _clean(self) -> None:
        if not self.data.get("username"):
            self.add_error("username", "This field is required.")
        p1 = self.data.get("password1", "")
        p2 = self.data.get("password2", "")
        if not p1:
            self.add_error("password1", "This field is required.")
        if not p2:
            self.add_error("password2", "This field is required.")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "The two password fields didn't match.")
        elif p1 and p2:
            try:
                from buraq.contrib.auth.password_validation import validate_password
                validate_password(p1)
            except ValidationError as e:
                for msg in (e.message if isinstance(e.message, list) else [str(e)]):
                    self.add_error("password1", str(msg))

    async def save(self):
        from buraq.contrib.auth import make_password
        from buraq.contrib.auth.models import User
        return await User.objects.create(
            username=self.data["username"],
            hashed_password=await make_password(self.data["password1"]),
        )


class SetPasswordForm(_BaseForm):
    """
    Form for setting a new password (no old-password check).
    Used in password-reset flows.
    """

    def __init__(self, user, data: dict | None = None):
        super().__init__(data)
        self.user = user

    def _clean(self) -> None:
        p1 = self.data.get("new_password1", "")
        p2 = self.data.get("new_password2", "")
        if not p1:
            self.add_error("new_password1", "This field is required.")
        if not p2:
            self.add_error("new_password2", "This field is required.")
        if p1 and p2 and p1 != p2:
            self.add_error("new_password2", "The two password fields didn't match.")
        elif p1 and p2:
            try:
                from buraq.contrib.auth.password_validation import validate_password
                validate_password(p1, self.user)
            except ValidationError as e:
                for msg in (e.message if isinstance(e.message, list) else [str(e)]):
                    self.add_error("new_password1", str(msg))

    async def save(self):
        from buraq.contrib.auth import make_password
        self.user.hashed_password = await make_password(self.data["new_password1"])
        await self.user.save()
        return self.user


class PasswordChangeForm(SetPasswordForm):
    """
    Form for changing a password — also requires the old password.
    """

    def _clean(self) -> None:
        super()._clean()
        old = self.data.get("old_password", "")
        if not old:
            self.add_error("old_password", "This field is required.")
            return
        from buraq.contrib.auth._passwords import verify_password
        if not verify_password(old, self.user.hashed_password):
            self.add_error("old_password", "Your old password was entered incorrectly.")


class AdminPasswordChangeForm(_BaseForm):
    """
    Form used in admin-style flows to set a user's password without knowing
    the current one (staff-only).
    """

    def __init__(self, user, data: dict | None = None):
        super().__init__(data)
        self.user = user

    def _clean(self) -> None:
        p1 = self.data.get("password1", "")
        p2 = self.data.get("password2", "")
        if not p1:
            self.add_error("password1", "This field is required.")
        if not p2:
            self.add_error("password2", "This field is required.")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "The two password fields didn't match.")
        elif p1 and p2:
            try:
                from buraq.contrib.auth.password_validation import validate_password
                validate_password(p1, self.user)
            except ValidationError as e:
                for msg in (e.message if isinstance(e.message, list) else [str(e)]):
                    self.add_error("password1", str(msg))

    async def save(self):
        from buraq.contrib.auth import make_password
        self.user.hashed_password = await make_password(self.data["password1"])
        await self.user.save()
        return self.user


__all__ = [
    "AuthenticationForm",
    "BaseUserCreationForm",
    "SetPasswordForm",
    "PasswordChangeForm",
    "AdminPasswordChangeForm",
]
