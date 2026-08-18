---
title: "Class-Based Views"
description: "get, post, put, patch, delete, head, options, trace"
---

## Base View

```python
from buraq.views import View
from buraq.shortcuts import render, redirect


class PostView(View):
    async def get(self, request, pk: int):
        post = await get_object_or_404(Post, id=pk)
        return await render(request, "posts/detail.html", {"post": post})

    async def post(self, request, pk: int):
        form = PostForm(data=dict(await request.form()))
        if await form.is_valid():
            await form.save()
            return redirect("/posts/")
        return await render(request, "posts/detail.html", {"form": form})
```

Register with `as_view()`:

```python title="posts/urls.py"
from buraq.urls import get, post

urlpatterns = [
    get("/<int:pk>",  PostView.as_view(), name="post_detail"),
    post("/<int:pk>", PostView.as_view()),
]
```

## Supported HTTP methods

`get`, `post`, `put`, `patch`, `delete`, `head`, `options`, `trace`

Any unregistered method returns `405 Method Not Allowed` automatically.

## Class attributes via `as_view()`

Pass configuration at URL registration time:

```python
class PostListView(View):
    paginate_by = 10

    async def get(self, request):
        ...

urlpatterns = [
    get("/", PostListView.as_view(paginate_by=20)),  # override
]
```

## Mixins

Build reusable behaviour by combining mixins:

```python
from buraq.views.generic import SingleObjectMixin, TemplateMixin, View


class PostWithSidebarView(SingleObjectMixin, TemplateMixin, View):
    model         = Post
    template_name = "posts/detail_with_sidebar.html"

    async def get(self, request, **kwargs):
        self.kwargs = kwargs
        obj      = await self.get_object()
        sidebar  = await Post.objects.filter(is_published=True).limit(5)
        ctx      = await self.get_context_data(post=obj, sidebar=sidebar)
        return await render(request, self.get_template_name(), ctx)
```
