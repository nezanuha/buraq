# Authentication

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
    return render(request, "auth/login.html")


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

    return render(request, "dashboard.html", {"user": request.user})
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
    return render(request, "dashboard.html", {"user": request.user})


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

# Raises ValidationError if too short or entirely numeric
validate_password("weakpass")

# Keep the user logged in after a password change
from buraq.contrib.auth import update_session_auth_hash
await update_session_auth_hash(request, user)
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
| `POST` | `/auth/login` | Login, returns `access_token` |
| `GET` | `/auth/me` | Current user profile (Bearer required) |

---

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
