# Sessions

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

```python title="config/settings.py"
SESSION_COOKIE_NAME     = "buraq_session"
SESSION_COOKIE_MAX_AGE  = 1209600    # 2 weeks in seconds
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "lax"      # "strict" | "lax" | "none"
SECRET_KEY              = "your-secret-key"  # used to sign session cookies
```

!!! tip
    Sessions are cookie-backed and HMAC-signed with `SECRET_KEY`. Data is stored in the cookie itself (not server-side), so keep session data small.

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
    return render(request, "dashboard.html", {"messages": messages})
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
