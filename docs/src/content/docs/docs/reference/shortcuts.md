---
title: "buraq.shortcuts — API Reference"
description: "Render a Jinja2 template and return an HTML response.

This is a coroutine — context processors may query the database, and every
query in Buraq is async. Always `await` it."
---

```python
from buraq.shortcuts import render, redirect, get_object_or_404, render_to_string
```

## render

```python
async def render(request, template_name: str, context: dict = None) -> HTMLResponse
```

Render a Jinja2 template and return an HTML response.

```python
return await render(request, "posts/list.html", {"posts": posts})
return await render(request, "posts/list.html")   # no context
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

## get_list_or_404

```python
async def get_list_or_404(model, **kwargs) -> list
```

Fetch a filtered list of objects, or raise HTTP 404 if the result is empty.

```python
from buraq.shortcuts import get_list_or_404

posts = await get_list_or_404(Post, is_published=True)
# raises 404 if no published posts exist
```

Use `get_object_or_404` when you need a single object; use `get_list_or_404` when you need at least one result from a filtered set.

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
