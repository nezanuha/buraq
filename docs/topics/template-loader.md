# Template Loader

`buraq.template.loader` provides functions for loading and rendering Jinja2 templates outside of views — useful for email bodies, background tasks, and partial rendering.

---

## Usage

```python
from buraq.template.loader import render_to_string, get_template, select_template
```

Or via the shortcut:

```python
from buraq.shortcuts import render_to_string
```

---

## render_to_string()

Render a template to a string. Accepts a single template name or a list (tries each in order).

```python
from buraq.template.loader import render_to_string

# Single template
html = render_to_string("emails/welcome.html", {"user": user})

# With request — injects it into context so template can use request.user etc.
html = render_to_string("partials/nav.html", {}, request=request)

# Try multiple templates — uses the first one that exists
html = render_to_string(
    ["widgets/custom.html", "widgets/default.html"],
    {"items": items},
)
```

### Common use case — sending HTML emails

```python
from buraq.template.loader import render_to_string
from buraq.contrib.email import send_mail

async def send_welcome_email(user):
    html_body = render_to_string("emails/welcome.html", {"user": user})
    text_body = render_to_string("emails/welcome.txt", {"user": user})

    await send_mail(
        subject="Welcome to Buraq!",
        message=text_body,
        html_message=html_body,
        recipient_list=[user.email],
    )
```

---

## get_template()

Load a template object by name. Raises `TemplateDoesNotExist` if not found.

```python
from buraq.template.loader import get_template, TemplateDoesNotExist

template = get_template("posts/detail.html")
html = template.render({"post": post})

# Handle missing template
try:
    template = get_template("optional/widget.html")
except TemplateDoesNotExist:
    html = ""
```

---

## select_template()

Try a list of template names and return the first one that exists. Raises `TemplateDoesNotExist` if none are found.

```python
from buraq.template.loader import select_template

# Pick a template based on the post type, fall back to default
template = select_template([
    f"posts/{post.type}.html",
    "posts/default.html",
])
html = template.render({"post": post})
```

---

## TemplateDoesNotExist

Raised by `get_template()` and `select_template()` when no matching template is found.

```python
from buraq.template.loader import TemplateDoesNotExist

try:
    html = render_to_string("missing.html", {})
except TemplateDoesNotExist as e:
    print(f"Template not found: {e}")
```

---

## In background tasks

`render_to_string()` works anywhere — no request context required:

```python
from buraq.template.loader import render_to_string

async def generate_report(report_id: int):
    report = await Report.objects.get(id=report_id)
    html = render_to_string("reports/pdf.html", {"report": report})
    await save_pdf(html, report_id)
```
