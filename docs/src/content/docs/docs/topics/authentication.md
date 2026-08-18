---
title: "Authentication"
description: "request.user is either a User instance (with is_authenticated = True) or an AnonymousUser (with is_authenticated = False)."
---

Buraq ships two complementary auth mechanisms that can coexist in the same project:

| Mechanism | When to use |
|---|---|
| **Session-based** (`AuthenticationMiddleware`) | Server-rendered pages, cookie sessions |
| **JWT** (`Authorization: Bearer …`) | APIs, mobile clients, SPA back-ends |

---

## Session-based authentication

### Setup

Add both middleware layers to your application (order matters — `AuthenticationMiddleware` wraps `SessionMiddleware`):

```python title="config/urls.py"
from buraq.contrib.auth.middleware import AuthenticationMiddleware
from buraq.contrib.sessions import SessionMiddleware
from buraq.conf import settings

app.add_middleware(AuthenticationMiddleware)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)
```

### Login / Logout views

```python
from buraq.contrib.auth import authenticate, login, logout
from buraq.shortcuts import redirect, render

async def login_view(request):
    if request.method == "POST":
        form = await request.form()
        user = await authenticate(
            request,
            username=form["username"],
            password=form["password"],
        )
        if user:
            await login(request, user)
            next_url = request.query_params.get("next", "/dashboard")
            return redirect(next_url)
        # Show error
    return await render(request, "auth/login.html")


async def logout_view(request):
    await logout(request)
    return redirect("/")
```

### authenticate()

```python
from buraq.contrib.auth import authenticate

user = await authenticate(request, username="alice", password="secret")
# Returns User instance on success, None on failure or inactive account
```

### login()

```python
from buraq.contrib.auth import login

await login(request, user)
# Writes _auth_user_id to session, updates last_login
```

### logout()

```python
from buraq.contrib.auth import logout

await logout(request)
# Flushes the entire session, sets request.user = AnonymousUser()
```

### request.user

After `AuthenticationMiddleware` runs, every request has `request.user`:

```python
async def dashboard(request):
    if not request.user.is_authenticated:
        return redirect("/auth/login")

    return await render(request, "dashboard.html", {"user": request.user})
```

`request.user` is either a `User` instance (with `is_authenticated = True`) or an `AnonymousUser` (with `is_authenticated = False`).

### AnonymousUser

```python
from buraq.contrib.auth.models import AnonymousUser

anon = AnonymousUser()
anon.is_authenticated  # False
anon.is_staff          # False
anon.is_superuser      # False
```

### Protecting views with decorators

```python
from buraq.decorators import login_required, staff_required, superuser_required, permission_required

@login_required
async def dashboard(request):
    return await render(request, "dashboard.html", {"user": request.user})


@login_required(login_url="/signin")
async def settings_view(request):
    ...


@staff_required
async def admin_view(request):
    ...


@superuser_required
async def super_view(request):
    ...


@permission_required("blog.publish_post")
async def publish_view(request, pk: int):
    ...
```

### @user_passes_test

Redirect based on any custom condition:

```python
from buraq.decorators import user_passes_test

@user_passes_test(lambda u: u.is_active and u.date_joined.year >= 2024)
async def new_users_only(request):
    ...
```

### Protecting class-based views

```python
from buraq.views.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"

class PublishView(PermissionRequiredMixin, UpdateView):
    model               = Post
    permission_required = "blog.publish_post"

class StaffOnlyView(UserPassesTestMixin, DetailView):
    model = Report

    async def test_func(self, request) -> bool:
        return request.user.is_staff
```

See [Auth Mixins](views/mixins.md) for the full reference.

---

### Permissions

Check whether a user holds a specific permission:

```python
# In a view
can_publish = await request.user.has_perm("blog.publish_post")
can_all     = await request.user.has_perms(["blog.add_post", "blog.change_post"])
any_blog    = await request.user.has_module_perms("blog")

# List user's direct permissions and groups
perms  = await request.user.user_permissions()
groups = await request.user.groups()
```

Superusers (`is_superuser=True`) always return `True` from all `has_perm*` checks.

See [Permissions & Groups](permissions.md) for setup and assignment.

---

### Password utilities

```python
from buraq.contrib.auth import make_password, check_password, validate_password

hashed = make_password("my-secret")
ok     = check_password("my-secret", hashed)

# Keep the user logged in after a password change
from buraq.contrib.auth import update_session_auth_hash
await update_session_auth_hash(request, user)
```

---

## Password validation

Buraq ships a set of password validators that run during registration and
password-change flows.  Configure them in settings:

```python title="config/settings.py"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "buraq.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "buraq.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "buraq.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "buraq.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "buraq.contrib.auth.password_validation.MaximumLengthValidator"},
]
```

### validate_password()

Call from registration or change-password views — raises `ValidationError`
listing all failures from all configured validators:

```python
from buraq.contrib.auth.password_validation import validate_password
from buraq.exceptions import ValidationError

try:
    validate_password("abc123", user=request.user)
except ValidationError as e:
    # e.messages → list of failure strings
    return await render(request, "auth/register.html", {"errors": e.messages})
```

### Available validators

| Class | Description | Default option |
|---|---|---|
| `MinimumLengthValidator` | Minimum number of characters | `min_length=8` |
| `CommonPasswordValidator` | Rejects commonly used passwords | — |
| `NumericPasswordValidator` | Rejects all-digit passwords | — |
| `UserAttributeSimilarityValidator` | Rejects passwords too similar to user fields | `max_similarity=0.7` |
| `MaximumLengthValidator` | Guards against DoS via bcrypt | `max_length=4096` |

### Custom validator

Implement `validate(password, user=None)` and optionally `get_help_text()`:

```python
class NoSpacesValidator:
    def validate(self, password, user=None):
        if " " in password:
            raise ValidationError("Password may not contain spaces.")

    def get_help_text(self):
        return "Your password may not contain spaces."
```

Register it just like a built-in validator:

```python
AUTH_PASSWORD_VALIDATORS = [
    ...,
    {"NAME": "myapp.validators.NoSpacesValidator"},
]
```

---

## Authentication backends

`authenticate()` iterates `AUTHENTICATION_BACKENDS` in order and returns the first user a backend yields.  The default backend checks the `User` table.

### Configuration

```python title="config/settings.py"
AUTHENTICATION_BACKENDS = [
    "myapp.backends.LDAPBackend",          # checked first
    "buraq.contrib.auth.backends.ModelBackend",  # fallback
]
```

### Built-in backends

| Backend | Behaviour |
|---|---|
| `buraq.contrib.auth.backends.ModelBackend` | Default. Checks `username` + `password` against the `User` table; rejects inactive users (`is_active=False`). |
| `buraq.contrib.auth.backends.AllowAllUsersModelBackend` | Like `ModelBackend` but **authenticates inactive users too**. Useful when you want to show a "your account is disabled" page after login rather than a generic invalid-credentials error. |
| `buraq.contrib.auth.backends.AllowAllUsersRemoteUserBackend` | Remote-user backend that authenticates inactive users. Pair with upstream authentication (e.g. nginx `auth_request`) when the proxy asserts the identity and Buraq should accept it regardless of `is_active`. |

```python title="config/settings.py"
AUTHENTICATION_BACKENDS = [
    "buraq.contrib.auth.backends.AllowAllUsersModelBackend",
]
```

### Writing a custom backend

A backend is any class with an async `authenticate` method.  `get_user` is optional but required for session restoration.

```python title="myapp/backends.py"
class LDAPBackend:
    async def authenticate(self, request, *, username: str, password: str):
        user = await ldap_lookup(username, password)   # returns User or None
        return user

    async def get_user(self, user_id: int):
        from buraq.contrib.auth.models import User
        return await User.objects.get_or_none(id=user_id)
```

`authenticate()` in views works unchanged — the backend selection is transparent:

```python
user = await authenticate(request, username="alice", password="secret")
```

`user._auth_backend` records which backend authenticated the user.

---

## JWT authentication

Useful for API endpoints consumed by mobile or SPA clients.

### Setup

```python title="config/settings.py"
SECRET_KEY         = "your-jwt-secret"
JWT_ALGORITHM      = "HS256"
JWT_EXPIRY_MINUTES = 60
```

```python title="config/urls.py"
urlpatterns = [
    path("/auth", include("buraq.contrib.auth.urls")),
]
```

### Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register` | Create a new user |
| `POST` | `/auth/login` | Exchange credentials for a token (`obtain_auth_token`) |
| `GET` | `/auth/me` | Current user profile (Bearer required) |

---

---

## Class-based auth views

Buraq ships ready-to-use class-based views for the full login/logout/password flow. Mount them with `path()` and supply the matching templates.

```python title="config/urls.py"
from buraq.contrib.auth.views import (
    LoginView, LogoutView,
    PasswordChangeView,
    PasswordResetView, PasswordResetConfirmView,
)

urlpatterns = [
    path("/auth/login",    LoginView.as_view(),   name="login"),
    path("/auth/logout",   LogoutView.as_view(),  name="logout"),
    path("/auth/password/change", PasswordChangeView.as_view(), name="password_change"),
    path("/auth/password/reset",  PasswordResetView.as_view(),  name="password_reset"),
    path("/auth/password/reset/{token}", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
]
```

### LoginView

| Attribute | Default | Description |
|---|---|---|
| `template_name` | `registration/login.html` | GET template |
| `redirect_field_name` | `"next"` | Query param for post-login redirect |
| `success_url` | `"/"` | Fallback redirect |
| `redirect_authenticated_user` | `False` | Skip login for already-authenticated users |

On POST, validates `username` + `password`, sets an `access_token` HttpOnly cookie, and redirects.

### LogoutView

| Attribute | Default |
|---|---|
| `next_page` | `"/"` |
| `template_name` | `registration/logged_out.html` |

Deletes the `access_token` cookie and redirects to `next_page`.

### PasswordChangeView

Accepts `old_password`, `new_password1`, `new_password2`. Validates the old password with Argon2 and updates `hashed_password` on success.

Template: `registration/password_change_form.html`

### PasswordResetView

Accepts an email address, looks up the user, generates a HMAC-SHA256–signed token (`uid-timestamp-sig`), and sends a reset link by email. Silently succeeds even for unknown addresses (prevents user enumeration). Token expires after 24 hours.

Template: `registration/password_reset_form.html`  
Email template: `registration/password_reset_email.html`

### PasswordResetConfirmView

Validates the signed token from the URL, verifies the HMAC, and sets the new password. Rejects expired (> 24 h) or tampered tokens with a clear error message.

Template: `registration/password_reset_confirm.html`

### PasswordResetDoneView / PasswordChangeDoneView / PasswordResetCompleteView

These three confirmation views display success pages after each step of the password flow. They render a template and accept no form input:

| View | Default template | Shown after |
|---|---|---|
| `PasswordResetDoneView` | `registration/password_reset_done.html` | Reset email sent |
| `PasswordChangeDoneView` | `registration/password_change_done.html` | Password changed |
| `PasswordResetCompleteView` | `registration/password_reset_complete.html` | Reset confirmed |

Mount them alongside the other auth views:

```python
from buraq.contrib.auth.views import (
    PasswordResetDoneView,
    PasswordChangeDoneView,
    PasswordResetCompleteView,
)

urlpatterns = [
    ...
    path("/auth/password/reset/done",     PasswordResetDoneView.as_view(),     name="password_reset_done"),
    path("/auth/password/change/done",    PasswordChangeDoneView.as_view(),    name="password_change_done"),
    path("/auth/password/reset/complete", PasswordResetCompleteView.as_view(), name="password_reset_complete"),
]
```

### PasswordResetTokenGenerator

The underlying token generator is available directly if you need to create or validate reset links from your own code:

```python
from buraq.contrib.auth import PasswordResetTokenGenerator

generator = PasswordResetTokenGenerator()

# Generate a token for a user
token = generator.make_token(user)   # e.g. "6b4t2c-abc12345..."

# Validate a token from a reset URL
is_valid = generator.check_token(user, token)   # → True / False
```

Tokens are HMAC-SHA256–signed and time-limited. The expiry window is controlled by `PASSWORD_RESET_TIMEOUT` in settings (default: 86 400 seconds / 24 hours):

```python title="config/settings.py"
PASSWORD_RESET_TIMEOUT = 3600  # 1 hour
```

---

## Custom user model

Buraq ships `AbstractBaseUser` and `AbstractUser` for building custom user models, and `PermissionsMixin` for adding group/permission support.

```python
from buraq.contrib.auth.models import AbstractBaseUser, PermissionsMixin

class StaffUser(AbstractBaseUser, PermissionsMixin):
    email    = models.EmailField(unique=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
```

Use `get_user_model()` anywhere you need a reference to the active user model — it respects `AUTH_USER_MODEL`:

```python
from buraq.contrib.auth.models import get_user_model

User = get_user_model()
user = await User.objects.get(email="alice@example.com")
```

`AbstractUser` is the concrete default user class (with `username`, `email`, `is_staff`, etc.) that you can subclass without reimplementing everything:

```python
from buraq.contrib.auth.models import AbstractUser

class Profile(AbstractUser):
    bio = models.TextField(blank=True)
```

## Creating users

```python
from buraq.contrib.auth.models import User
from buraq.core.auth import hash_password

user = await User.objects.create(
    username        = "alice",
    email           = "alice@example.com",
    hashed_password = hash_password("secure-password"),
    is_active       = True,
)
```

## Creating a superuser via CLI

```bash
buraq createsuperuser
```

## User model fields

| Field | Type | Description |
|---|---|---|
| `username` | `str` | Unique username |
| `email` | `str` | Unique email |
| `hashed_password` | `str` | Argon2 hash |
| `is_active` | `bool` | Can log in (default: `True`) |
| `is_staff` | `bool` | Admin panel access |
| `is_superuser` | `bool` | All permissions |
| `is_authenticated` | `bool` | Always `True` for real users |
| `date_joined` | `datetime` | Account creation time |
| `last_login` | `datetime` | Updated on each `login()` call |
