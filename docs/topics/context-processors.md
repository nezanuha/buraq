# Context Processors

Context processors are callables that inject data into every template context automatically, so you don't repeat the same variables in every view.

## Built-in processors

| Processor | Injects | Default |
|---|---|---|
| `buraq.template.context_processors.request` | `{{ request }}` | Yes |
| `buraq.template.context_processors.auth` | `{{ user }}` | Yes |
| `buraq.template.context_processors.debug` | `{{ DEBUG }}` | No |
| `buraq.template.context_processors.i18n` | `{{ LANGUAGE_CODE }}` | No |

## Configuration

```python
# settings.py
TEMPLATE_CONTEXT_PROCESSORS = [
    "buraq.template.context_processors.request",
    "buraq.template.context_processors.auth",
    "buraq.template.context_processors.debug",
    "buraq.template.context_processors.i18n",
    "myapp.context_processors.site_settings",
]
```

## Writing a custom processor

```python
# myapp/context_processors.py

async def site_settings(request) -> dict:
    from buraq.contrib.sites.models import Site
    site = await Site.get_current(request)
    return {"site": site}
```

Both sync and async processors are supported. Async processors are awaited automatically.

## Using in views

Call `run_context_processors` to merge all processors into a context dict:

```python
from buraq.template.context_processors import run_context_processors

async def my_view(request):
    ctx = await run_context_processors(request)
    ctx["posts"] = await Post.objects.filter(published=True).all()
    return templates.TemplateResponse(request, "posts/list.html", ctx)
```

## Using in templates

After processors run, their variables are available in any template:

```html
<p>Hello, {{ user.username }}</p>
<p>Language: {{ LANGUAGE_CODE }}</p>
```
