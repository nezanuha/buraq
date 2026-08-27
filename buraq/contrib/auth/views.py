from fastapi import HTTPException, Request

from buraq.contrib.auth import check_password, make_password

from .models import User
from .schemas import UserCreate, UserRead


async def register(payload: UserCreate) -> UserRead:
    from sqlalchemy.exc import IntegrityError
    try:
        return await User.objects.create(
            email=payload.email,
            username=payload.username,
            first_name=payload.first_name,
            last_name=payload.last_name,
            hashed_password=await make_password(payload.password),
        )
    except IntegrityError as exc:
        msg = str(exc).lower()
        if "email" in msg:
            raise HTTPException(status_code=400, detail="Email already registered") from exc
        if "username" in msg:
            raise HTTPException(status_code=400, detail="Username already taken") from exc
        raise HTTPException(
            status_code=400, detail="Registration failed due to a conflict."
        ) from exc


# ── Class-based auth views ───────────────────────────────────────────────────

def _set_access_token(response, user) -> None:
    """
    Attach the access token alongside the session cookie.

    A browser gets it as an HttpOnly cookie and never has to think about it; a
    client that would rather send ``Authorization: Bearer`` can read the same
    token from a login response. Both are verified without touching the database.
    """
    from buraq.conf import settings
    from buraq.contrib.auth.tokens import token_for_user

    minutes = getattr(settings, "JWT_EXPIRY_MINUTES", 60)
    response.set_cookie(
        "access_token",
        token_for_user(user),
        max_age=minutes * 60,
        httponly=True,
        samesite="lax",
        secure=not settings.DEBUG,
    )


class LoginView:
    """
    Template-based login view — renders a login form on GET, authenticates on POST.

    Usage:
        from buraq.urls import get, post
        from buraq.contrib.auth.views import LoginView

        urlpatterns = [
            get("/login",  LoginView.as_view(), name="login"),
            post("/login", LoginView.as_view()),
        ]

    Requires a template at ``registration/login.html`` with a form that POSTs
    ``username`` and ``password`` fields.
    """

    template_name: str = "registration/login.html"
    redirect_field_name: str = "next"
    success_url: str = "/"
    redirect_authenticated_user: bool = False

    @classmethod
    def as_view(cls, **initkwargs):
        view = cls(**initkwargs)

        async def _view(request: Request, **kwargs):
            return await view.dispatch(request, **kwargs)

        _view.view_class = cls
        _view.view_initkwargs = initkwargs
        return _view

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    async def dispatch(self, request, **kwargs):
        if request.method == "GET":
            return await self.get(request, **kwargs)
        return await self.post(request, **kwargs)

    def get_success_url(self, request) -> str:
        return request.query_params.get(self.redirect_field_name, self.success_url)

    async def get(self, request, **kwargs):
        from buraq.shortcuts import render
        return await render(request, self.template_name, {
            "next": request.query_params.get(self.redirect_field_name, ""),
        })

    async def post(self, request, **kwargs):
        from buraq.contrib.auth import authenticate, login
        from buraq.shortcuts import redirect, render
        form_data = dict(await request.form())
        username = form_data.get("username", "")
        password = form_data.get("password", "")

        user = await authenticate(request, username=username, password=password)
        if user:
            await login(request, user)
            response = redirect(self.get_success_url(request))
            _set_access_token(response, user)
            return response

        return await render(request, self.template_name, {
            "error": "Invalid username or password.",
            "next": form_data.get(self.redirect_field_name, ""),
        })


class LogoutView:
    """
    Logs out the current user by clearing the session/cookie.

    Usage:
        post("/logout", LogoutView.as_view(), name="logout")
    """

    next_page: str = "/"
    template_name: str = "registration/logged_out.html"
    http_method_names = ["get", "post"]

    @classmethod
    def as_view(cls, **initkwargs):
        view = cls(**initkwargs)

        async def _view(request: Request, **kwargs):
            return await view.dispatch(request, **kwargs)

        _view.view_class = cls
        return _view

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    async def dispatch(self, request, **kwargs):
        return await self.get(request, **kwargs)

    async def get(self, request, **kwargs):
        from buraq.contrib.auth import logout
        from buraq.shortcuts import redirect
        await logout(request)
        response = redirect(self.next_page)
        # Clearing the session is not enough: the access token authenticates on
        # its own, so a logout that left it in place would not log anyone out.
        response.delete_cookie("access_token")
        return response


class PasswordChangeView:
    """
    Allows an authenticated user to change their password.

    Template: ``registration/password_change_form.html``
    Expects POST fields: ``old_password``, ``new_password1``, ``new_password2``
    """

    template_name: str = "registration/password_change_form.html"
    success_url: str = "/auth/password-change/done/"

    @classmethod
    def as_view(cls, **initkwargs):
        view = cls(**initkwargs)

        async def _view(request: Request, **kwargs):
            return await view.dispatch(request, **kwargs)

        _view.view_class = cls
        return _view

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    async def dispatch(self, request, **kwargs):
        if request.method == "GET":
            return await self.get(request, **kwargs)
        return await self.post(request, **kwargs)

    async def get(self, request, **kwargs):
        from buraq.shortcuts import render
        return await render(request, self.template_name, {})

    async def post(self, request, **kwargs):
        from buraq.shortcuts import redirect, render
        form_data = dict(await request.form())
        old_pw = form_data.get("old_password", "")
        new_pw1 = form_data.get("new_password1", "")
        new_pw2 = form_data.get("new_password2", "")

        errors = []
        user_id = getattr(getattr(request, "user", None), "id", None)
        if not user_id:
            errors.append("You must be logged in to change your password.")
        else:
            user = await User.objects.get_or_none(id=user_id)
            if not user or not await check_password(old_pw, user.hashed_password):
                errors.append("Your old password was entered incorrectly.")
            elif new_pw1 != new_pw2:
                errors.append("The two password fields didn't match.")
            elif not new_pw1:
                errors.append("New password cannot be empty.")
            else:
                await User.objects.update(user.id, hashed_password=await make_password(new_pw1))
                return redirect(self.success_url)

        return await render(request, self.template_name, {"errors": errors})


class PasswordResetView:
    """
    Sends a password-reset email with a signed token link.

    Template: ``registration/password_reset_form.html``
    Email template: ``registration/password_reset_email.html``
    """

    template_name: str = "registration/password_reset_form.html"
    email_template_name: str = "registration/password_reset_email.html"
    success_url: str = "/auth/password-reset/done/"
    from_email: str | None = None

    @classmethod
    def as_view(cls, **initkwargs):
        view = cls(**initkwargs)

        async def _view(request: Request, **kwargs):
            return await view.dispatch(request, **kwargs)

        _view.view_class = cls
        return _view

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    async def dispatch(self, request, **kwargs):
        if request.method == "GET":
            return await self.get(request, **kwargs)
        return await self.post(request, **kwargs)

    async def get(self, request, **kwargs):
        from buraq.shortcuts import render
        return await render(request, self.template_name, {})

    async def post(self, request, **kwargs):
        import hashlib
        import hmac
        import time

        from buraq.conf import settings
        from buraq.contrib.email.send import send_mail
        from buraq.shortcuts import redirect

        form_data = dict(await request.form())
        email = form_data.get("email", "").strip().lower()
        user = await User.objects.get_or_none(email=email)

        if user:
            # Build a signed token: uid:timestamp:signature
            timestamp = str(int(time.time()))
            raw = f"{user.id}:{user.email}:{timestamp}"
            sig = hmac.new(
                settings.SECRET_KEY.encode(),
                raw.encode(),
                hashlib.sha256,
            ).hexdigest()[:24]
            token = f"{user.id}-{timestamp}-{sig}"

            scheme = request.url.scheme
            host = request.headers.get("host", "localhost")
            reset_url = f"{scheme}://{host}/auth/password-reset/confirm/{token}/"

            try:
                body = render_to_string_safe(
                    self.email_template_name,
                    {"user": user, "reset_url": reset_url},
                    request,
                )
            except Exception:
                body = f"Click the link to reset your password: {reset_url}"

            await send_mail(
                subject="Password reset",
                message=body,
                from_email=self.from_email,
                recipient_list=[user.email],
            )

        return redirect(self.success_url)


class PasswordResetConfirmView:
    """
    Validates the reset token and sets a new password.

    Template: ``registration/password_reset_confirm.html``
    """

    template_name: str = "registration/password_reset_confirm.html"
    success_url: str = "/auth/password-reset/complete/"

    @classmethod
    def as_view(cls, **initkwargs):
        view = cls(**initkwargs)

        async def _view(request: Request, **kwargs):
            return await view.dispatch(request, **kwargs)

        _view.view_class = cls
        return _view

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    async def dispatch(self, request, **kwargs):
        if request.method == "GET":
            return await self.get(request, **kwargs)
        return await self.post(request, **kwargs)

    def _verify_token(self, token: str):
        import time

        from buraq.conf import settings

        try:
            parts = token.split("-")
            if len(parts) < 3:
                return None
            uid = parts[0]
            timestamp = parts[1]
            sig = "-".join(parts[2:])
            timeout = getattr(settings, "PASSWORD_RESET_TIMEOUT", 259200)
            if int(time.time()) - int(timestamp) > timeout:
                return None
            return uid, timestamp, sig
        except (ValueError, IndexError):
            return None

    async def get(self, request, **kwargs):
        from buraq.shortcuts import render
        token = kwargs.get("token", "")
        valid = self._verify_token(token) is not None
        return await render(request, self.template_name, {"valid": valid, "token": token})

    async def post(self, request, **kwargs):
        import hashlib
        import hmac

        from buraq.conf import settings
        from buraq.shortcuts import redirect, render

        form_data = dict(await request.form())
        token = kwargs.get("token", form_data.get("token", ""))
        parsed = self._verify_token(token)

        if not parsed:
            return await render(request, self.template_name, {
                "valid": False, "error": "The reset link is invalid or has expired."
            })

        uid, timestamp, sig = parsed
        user = await User.objects.get_or_none(id=int(uid))
        if not user:
            return await render(request, self.template_name, {"valid": False})

        # Verify signature
        raw = f"{user.id}:{user.email}:{timestamp}"
        expected = hmac.new(
            settings.SECRET_KEY.encode(),
            raw.encode(),
            hashlib.sha256,
        ).hexdigest()[:24]
        if not hmac.compare_digest(sig, expected):
            return await render(request, self.template_name, {
                "valid": False, "error": "Invalid reset token."
            })

        pw1 = form_data.get("new_password1", "")
        pw2 = form_data.get("new_password2", "")
        if pw1 != pw2:
            return await render(request, self.template_name, {
                "valid": True, "token": token,
                "error": "The two passwords didn't match.",
            })
        if not pw1:
            return await render(request, self.template_name, {
                "valid": True, "token": token,
                "error": "Password cannot be empty.",
            })

        await User.objects.update(user.id, hashed_password=await make_password(pw1))
        return redirect(self.success_url)


class PasswordResetDoneView:
    """
    Shown after a password-reset email has been sent.

    Template: ``registration/password_reset_done.html``
    """

    template_name: str = "registration/password_reset_done.html"

    @classmethod
    def as_view(cls, **initkwargs):
        view = cls(**initkwargs)

        async def _view(request: Request, **kwargs):
            from buraq.shortcuts import render
            return await render(request, view.template_name, {})

        _view.view_class = cls
        return _view

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class PasswordChangeDoneView:
    """
    Shown after a successful password change.

    Template: ``registration/password_change_done.html``
    """

    template_name: str = "registration/password_change_done.html"

    @classmethod
    def as_view(cls, **initkwargs):
        view = cls(**initkwargs)

        async def _view(request: Request, **kwargs):
            from buraq.shortcuts import render
            return await render(request, view.template_name, {})

        _view.view_class = cls
        return _view

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class PasswordResetCompleteView:
    """
    Shown after a successful password reset.

    Template: ``registration/password_reset_complete.html``
    """

    template_name: str = "registration/password_reset_complete.html"

    @classmethod
    def as_view(cls, **initkwargs):
        view = cls(**initkwargs)

        async def _view(request: Request, **kwargs):
            from buraq.shortcuts import render
            return await render(request, view.template_name, {})

        _view.view_class = cls
        return _view

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def render_to_string_safe(template_name, context=None, request=None) -> str:
    try:
        from buraq.template.loader import render_to_string
        return render_to_string(template_name, context, request)
    except Exception:
        return ""
