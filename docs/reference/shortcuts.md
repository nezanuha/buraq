# buraq.shortcuts — API Reference

```python
from buraq.shortcuts import render, redirect, get_object_or_404, render_to_string
```

## render

```python
def render(request, template_name: str, context: dict = None) -> HTMLResponse
```

Render a Jinja2 template and return an HTML response.

```python
return render(request, "posts/list.html", {"posts": posts})
return render(request, "posts/list.html")   # no context
```

## redirect

```python
def redirect(to: str, permanent: bool = False) -> RedirectResponse
```

Return an HTTP redirect response.

```python
return redirect("/posts/")
return redirect("/posts/", permanent=True)   # 301 Moved Permanently
```

## get_object_or_404

```python
async def get_object_or_404(model, **kwargs) -> model_instance
```

Fetch a single object matching `kwargs`, or raise HTTP 404.

```python
post = await get_object_or_404(Post, id=pk)
post = await get_object_or_404(Post, slug=slug, is_published=True)
```

## render_to_string

```python
def render_to_string(
    template_name: str | list[str],
    context: dict = None,
    request=None,
) -> str
```

Render a template to a string without returning an HTTP response. Accepts a single template name or a list (tries each in order).

```python
from buraq.shortcuts import render_to_string

html = render_to_string("emails/welcome.html", {"user": user})

# Try multiple templates — first one that exists wins
html = render_to_string(["widgets/custom.html", "widgets/default.html"], {"items": items})
```

See [Template Loader](../topics/template-loader.md) for the full API including `get_template()` and `select_template()`.
