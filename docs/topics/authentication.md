# Authentication

## Setup

```python title="config/settings.py"
INSTALLED_APPS = ["buraq.contrib.auth", ...]

SECRET_KEY         = "your-jwt-secret"
JWT_ALGORITHM      = "HS256"
JWT_EXPIRY_MINUTES = 60
```

```python title="config/urls.py"
urlpatterns = [
    path("/auth", include("buraq.contrib.auth.urls")),
]
```

## Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register` | Create a new user |
| `POST` | `/auth/login` | Login, returns `access_token` |
| `GET` | `/auth/me` | Current user profile |

## Protecting views

```python
from buraq.decorators import login_required, permission_required


@login_required
async def dashboard(request):
    return render(request, "dashboard.html", {"user": request.user})


@login_required(redirect_url="/auth/login")
async def settings_view(request):
    ...


@permission_required("posts.publish")
async def publish_post(request, pk: int):
    ...
```

## Accessing the user

```python
async def profile(request):
    user = request.user
    if user is None:
        return redirect("/auth/login")

    return render(request, "profile.html", {
        "username": user.username,
        "email":    user.email,
        "is_staff": user.is_staff,
    })
```

## Creating users programmatically

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
| `hashed_password` | `str` | bcrypt hash |
| `is_active` | `bool` | Can login (default: True) |
| `is_staff` | `bool` | Admin panel access |
| `is_superuser` | `bool` | All permissions |
| `created_at` | `datetime` | Account creation time |
