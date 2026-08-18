---
title: "Function-Based Views"
description: "The simplest way to write views. An FBV is just an async def that takes a request and returns a response."
---

The simplest way to write views. An FBV is just an `async def` that takes a `request` and returns a response.

## Basic view

```python
from buraq.shortcuts import render


async def post_list(request):
    posts = await Post.objects.filter(is_published=True)
    return await render(request, "posts/list.html", {"posts": posts})
```

## Path parameters

Type-annotate path params — Buraq injects them from the URL:

```python
async def post_detail(request, slug: str):
    post = await get_object_or_404(Post, slug=slug)
    return await render(request, "posts/detail.html", {"post": post})


async def post_by_id(request, pk: int):
    post = await get_object_or_404(Post, id=pk)
    return await render(request, "posts/detail.html", {"post": post})
```

## Handling methods

```python
async def post_form(request, pk: int = None):
    if request.method == "POST":
        form = PostForm(data=dict(await request.form()))
        if await form.is_valid():
            await form.save()
            return redirect("/posts/")
    else:
        instance = await Post.objects.get(id=pk) if pk else None
        form = PostForm(instance=instance)

    return await render(request, "posts/form.html", {"form": form})
```

## Request object

```python
async def my_view(request):
    # Method
    request.method          # "GET", "POST", etc.

    # Path & URL
    request.url             # full URL object
    request.url.path        # "/posts/1/edit"

    # Query string
    request.query_params.get("page", 1)
    request.query_params.getlist("tags")

    # Headers
    request.headers.get("content-type")

    # Body
    body   = await request.body()            # raw bytes
    json   = await request.json()            # parsed JSON
    form   = dict(await request.form())     # form data

    # Auth
    request.user            # current user (or None)

    # Session
    request.session         # dict-like session
    request.session["key"] = "value"

    # Client
    request.client.host     # client IP
```

## Returning responses

```python
from buraq.shortcuts import render, redirect
from starlette.responses import JSONResponse, Response


async def my_view(request):
    # HTML response
    return await render(request, "template.html", {"key": "value"})

    # Redirect
    return redirect("/posts/")
    return redirect("/posts/", permanent=True)   # 301

    # JSON
    return JSONResponse({"key": "value"})
    return JSONResponse({"error": "not found"}, status_code=404)

    # Plain text
    return Response("OK", media_type="text/plain")
```

## Shortcuts

```python
from buraq.shortcuts import get_object_or_404

# Raises HTTP 404 if not found
post = await get_object_or_404(Post, slug=slug)
post = await get_object_or_404(Post, id=pk, is_published=True)
```

## Decorators

Decorators are importable two ways. `buraq.decorators` is a single flat
namespace holding all of them, and there are per-concern modules mirroring
Django so existing imports keep working:

| Concern | Django-compatible path |
|---|---|
| Auth | `buraq.contrib.auth.decorators` |
| HTTP methods | `buraq.views.decorators.http` |
| Caching | `buraq.views.decorators.cache` |
| CSRF | `buraq.views.decorators.csrf` |
| Vary headers | `buraq.views.decorators.vary` |
| CSP | `buraq.views.decorators.csp` |

Both styles return the same objects — pick whichever suits your project.

```python
from buraq.decorators import login_required, permission_required


@login_required
async def create_post(request):
    ...


@login_required(redirect_url="/auth/login")
async def edit_post(request, pk: int):
    ...


@permission_required("posts.publish")
async def publish_post(request, pk: int):
    ...
```

## csrf_exempt

```python
from buraq.decorators import csrf_exempt

@csrf_exempt
async def webhook(request):
    """Third-party webhooks don't send CSRF tokens."""
    payload = await request.json()
    ...
```

`csrf_exempt` marks the view with `_csrf_exempt = True`. The CSRF middleware skips validation for such views.

## never_cache

```python
from buraq.decorators import never_cache

@never_cache
async def user_dashboard(request):
    ...
```

Adds `Cache-Control: no-store`, `Pragma: no-cache`, and `Expires: 0` headers to every response — prevents browsers and proxies from caching sensitive pages.
