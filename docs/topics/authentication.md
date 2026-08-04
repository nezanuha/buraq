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
from buraq.decorators import login_required, staff_required, superuser_required

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
```

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
