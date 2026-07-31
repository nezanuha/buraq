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

Flash messages use the session internally:

```python
from buraq.contrib.messages import success, error, warning, info


async def create_post(request):
    # ... save post ...
    success(request, "Post created successfully!")
    return redirect("/posts/")
```

In templates:

```html+jinja
{% for message in get_messages(request) %}
  <div class="alert alert-{{ message.level }}">{{ message.text }}</div>
{% endfor %}
```
