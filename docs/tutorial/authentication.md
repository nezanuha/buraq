# Part 5 — Authentication

Buraq includes JWT-based authentication out of the box.

## Setup

```python title="config/settings.py"
INSTALLED_APPS = [
    "buraq.contrib.auth",
    "posts",
]

SECRET_KEY         = "your-secret-key"
JWT_ALGORITHM      = "HS256"
JWT_EXPIRY_MINUTES = 60
```

```python title="config/urls.py"
urlpatterns = [
    path("/auth", include("buraq.contrib.auth.urls")),
    path("/posts", include("posts.urls")),
]
```

This adds these endpoints automatically:

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register` | Register a new user |
| `POST` | `/auth/login` | Login and get JWT token |
| `GET` | `/auth/me` | Get current user profile |
| `POST` | `/auth/logout` | Logout |

## Protecting views

```python
from buraq.decorators import login_required, permission_required


@login_required
async def create_post(request):
    # request.user is available here
    ...


@permission_required("posts.publish")
async def publish_post(request, pk: int):
    ...
```

## Accessing the current user

```python
async def my_view(request):
    user = request.user
    if user:
        print(user.username, user.email)
```

## Creating a superuser

```bash
buraq createsuperuser
```

## Register & login flow

```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "email": "alice@example.com", "password": "secret123"}'

# Login — returns a JWT token
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "secret123"}'
# → {"access_token": "eyJ...", "token_type": "bearer"}

# Use the token
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer eyJ..."
```
