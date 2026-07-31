# buraq.shortcuts — API Reference

```python
from buraq.shortcuts import render, redirect, get_object_or_404
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
