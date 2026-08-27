---
title: "Sessions"
description: "Sessions are cookie-backed and HMAC-signed with SECRET_KEY. Data is stored in the cookie itself (not server-side), so keep session data small."
---

## Reading and writing

```python
async def my_view(request):
    # Read
    username = request.session.get("username")
    cart     = request.session.get("cart", [])

    # Write
    request.session["username"] = "alice"
    request.session["cart"]     = [1, 2, 3]

    # Delete a key
    request.session.pop("temp_data", None)

    # Clear all session data
    request.session.clear()
```

## Configuration

The default `SessionMiddleware` stores all session data in a signed cookie. Configure it in `main.py`:

```python title="main.py"
from buraq.contrib.sessions import SessionMiddleware
from buraq.conf import settings

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,  # required — signs the cookie
    session_cookie="session",        # cookie name (default: "session")
    max_age=1209600,                 # seconds until expiry (default: 2 weeks)
    same_site="lax",                 # "strict" | "lax" | "none"
    https_only=False,                # True in production
    domain=None,                     # e.g. ".example.com" for subdomains
)
```

```python title="config/settings.py"
SECRET_KEY = "your-secret-key"   # used to sign session cookies
```

:::tip
Sessions are cookie-backed and HMAC-signed with `SECRET_KEY`. Data is stored in the cookie itself (not server-side), so keep session data small.
:::

## Server-side session backends

By default sessions are stored in a signed cookie. For larger session data or server-side expiry, switch to a server-side backend.

### File backend

```python title="config/settings.py"
SESSION_ENGINE    = "buraq.contrib.sessions.backends.file"
SESSION_FILE_PATH = "/tmp/buraq_sessions"   # optional, defaults to /tmp/buraq_sessions
```

Each session is stored as a JSON file. Files are cleaned up on access if expired.

:::note
`clear_expired()` on the file backend is an `async` method. Call it with `await` from any async context or management command.
:::

### Database backend

```python title="config/settings.py"
INSTALLED_APPS = [
    ...,
    "buraq.contrib.sessions",
]

SESSION_ENGINE = "buraq.contrib.sessions.backends.db"
```

The `buraq_sessions` table comes from the app's own migration:

```bash
buraq migrate
```

Remove expired sessions periodically:

```bash
python manage.py clearsessions
```

### Cache backend

```python title="config/settings.py"
SESSION_ENGINE       = "buraq.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS  = "default"   # which CACHES entry to use
```

The `CachedSessionBackend` stores session data in whatever cache alias `SESSION_CACHE_ALIAS` points to. Sessions expire automatically when the cache TTL elapses — no cleanup needed.

### Using server-side backends in views

All backends share the same `SessionBase` async API. When using `ServerSessionMiddleware`, access the session directly via `request.session` (a dict-like object). To use a backend directly in an async context:

```python
from buraq.contrib.sessions.backends.file import FileSessionBackend

# "sessionid" is the default cookie name set by ServerSessionMiddleware
backend = FileSessionBackend(session_key=request.cookies.get("sessionid"))
await backend.set("cart", [1, 2, 3])
await backend.save()

cart = await backend.get("cart")
await backend.flush()      # clear and delete
await backend.cycle_key()  # rotate key (keeps data)
```

### Truthiness

`SessionBase` instances are truthy when the session cache contains data and falsy when empty or not yet loaded:

```python
backend = FileSessionBackend(session_key=key)
await backend.load()

if backend:
    # session has data
    ...
```

This lets you write simple `if session:` guards without calling `len()` or checking individual keys.

## `ServerSessionMiddleware` — server-side sessions with revocation

For security-sensitive apps (e.g. API keys, payment flows) that need the ability to forcibly revoke a session server-side, use `ServerSessionMiddleware` instead of the default cookie-based `SessionMiddleware`.

```python title="config/settings.py"
SESSION_ENGINE = "buraq.contrib.sessions.backends.db"  # or cache / file
```

```python title="main.py"
from buraq.contrib.sessions import ServerSessionMiddleware

app.add_middleware(
    ServerSessionMiddleware,
    session_cookie="sessionid",      # cookie name (default: "sessionid")
    max_age=None,                    # seconds; None uses SESSION_COOKIE_AGE (2 weeks)
    same_site="lax",                 # "strict" | "lax" | "none"
    https_only=not settings.DEBUG,   # True in production
    domain=None,                     # e.g. ".example.com" for subdomains
)
```

`ServerSessionMiddleware` reads `SESSION_ENGINE` from settings and loads that backend automatically. No `secret_key` is needed — the session ID in the cookie is opaque and the data lives server-side.

### Session key

With `ServerSessionMiddleware`, `request.session` exposes a `session_key` attribute — the server-side identifier stored in the backend:

```python
key = request.session.session_key   # e.g. "abcdef1234..."
```

### `set_expiry()` — per-session TTL

Override the default `SESSION_COOKIE_AGE` (2 weeks) for the current session:

```python
# Expire in 30 minutes
request.session.set_expiry(1800)

# Expire immediately on the next response (max_age=0 — browser deletes cookie)
request.session.set_expiry(0)

# Restore to the default SESSION_COOKIE_AGE (1 209 600 s)
request.session.set_expiry(None)
```

:::note
`set_expiry(0)` sets `max_age=0` on the cookie, which tells the browser to delete it immediately. It does **not** mean "expire when the browser closes". To get browser-session behaviour (no persistent cookie), pass `max_age=None` to the middleware constructor.
:::

### `revoke_session()` — force-expire a session

Revoke any session by its key — even from a different request (e.g. an admin action or a background job):

```python
from buraq.contrib.sessions import revoke_session

# Immediately delete the session from the backend
await revoke_session(session_key)
```

Use this for:

- **Security incidents** — log out a compromised account across all devices
- **Subscription cancellation** — revoke access as soon as payment fails
- **Admin-initiated logout** — force a specific user session to end

```python
# In a webhook handler: revoke all sessions for a user
async def handle_payment_failed(user):
    sessions = await get_all_sessions_for_user(user)
    for key in sessions:
        await revoke_session(key)
```

---

## Flash messages

Flash messages survive a redirect because they are stored in the session and consumed on the next request.

### Shortcut functions

```python
from buraq.contrib.messages import debug, info, success, warning, error

async def create_post(request):
    await Post.objects.create(...)
    success(request, "Post created successfully!")
    return redirect("/posts/")

async def delete_post(request, pk: int):
    await Post.objects.delete(pk)
    warning(request, "Post deleted.")
    return redirect("/posts/")
```

### add_message() — custom level

```python
from buraq.contrib.messages import add_message, SUCCESS, WARNING, ERROR, INFO, DEBUG

add_message(request, SUCCESS, "Saved.", extra_tags="toast")
add_message(request, ERROR, "Something went wrong.", extra_tags="modal")
```

`extra_tags` is a free-form string you can use for CSS classes or JS hooks.

### get_messages() — consume in a view

Messages are cleared from the session the moment `get_messages()` is called:

```python
from buraq.contrib.messages import get_messages

async def dashboard(request):
    messages = get_messages(request)   # list[Message]; session entry removed
    return await render(request, "dashboard.html", {"messages": messages})
```

### Message object

Each `Message` has:

| Attribute | Type | Description |
|---|---|---|
| `level` | `int` | Numeric level constant |
| `message` | `str` | The text |
| `extra_tags` | `str` | Extra CSS / hook tags |
| `tags` | `str` | Level name + extra_tags, space-separated |

### Level constants

| Constant | Value | Shortcut |
|---|---|---|
| `DEBUG` | 10 | `debug()` |
| `INFO` | 20 | `info()` |
| `SUCCESS` | 25 | `success()` |
| `WARNING` | 30 | `warning()` |
| `ERROR` | 40 | `error()` |

### In templates (Jinja2)

```html+jinja
{% for message in messages %}
  <div class="alert alert-{{ message.tags }}">{{ message.message }}</div>
{% endfor %}
```

Pass messages from the view context, or use a context processor to make `get_messages(request)` available globally.
