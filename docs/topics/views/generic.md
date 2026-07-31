# Generic Class-Based Views

Buraq provides Django-style generic views for the most common patterns.

## ListView

Display a list of objects:

```python
from buraq.views.generic import ListView


class PostListView(ListView):
    model         = Post
    template_name = "posts/list.html"
    paginate_by   = 10              # enables pagination
    ordering      = ["-created_at"]

    # Template context: object_list, post_list, paginator, page_obj, is_paginated
```

Custom queryset:

```python
class PublishedPostListView(ListView):
    model         = Post
    template_name = "posts/list.html"

    async def get_queryset(self):
        return await Post.objects.filter(is_published=True).order_by("-created_at")
```

## DetailView

Display a single object by `pk` or `slug`:

```python
class PostDetailView(DetailView):
    model         = Post
    template_name = "posts/detail.html"
    pk_url_kwarg  = "pk"     # URL param name (default: "pk")

    # Template context: object, post (model name lowercased)
```

## CreateView

Display a form and create a new object on POST:

```python
class PostCreateView(CreateView):
    model         = Post
    form_class    = PostForm
    template_name = "posts/form.html"
    success_url   = "/posts/"
```

## UpdateView

Display a pre-filled form and update an existing object on POST:

```python
class PostUpdateView(UpdateView):
    model         = Post
    form_class    = PostForm
    template_name = "posts/form.html"
    success_url   = "/posts/"
```

## DeleteView

Confirm and delete an object:

```python
class PostDeleteView(DeleteView):
    model         = Post
    template_name = "posts/confirm_delete.html"
    success_url   = "/posts/"
```

## TemplateView

Render a template with optional extra context:

```python
from buraq.views.generic import TemplateView


class AboutView(TemplateView):
    template_name = "about.html"
    extra_context = {"title": "About Us"}
```

## RedirectView

```python
from buraq.views.generic import RedirectView

urlpatterns = [
    get("/old-url/", RedirectView.as_view(url="/new-url/", permanent=True)),
]
```

## Overriding context

```python
class PostDetailView(DetailView):
    model         = Post
    template_name = "posts/detail.html"

    async def get_context_data(self, **kwargs):
        ctx      = await super().get_context_data(**kwargs)
        ctx["related"] = await Post.objects.filter(is_published=True).limit(3)
        return ctx
```

## URL registration

```python
urlpatterns = [
    get("/",                 PostListView.as_view(),   name="post_list"),
    get("/<str:slug>",       PostDetailView.as_view(), name="post_detail"),
    get("/new",              PostCreateView.as_view(), name="post_create"),
    post("/new",             PostCreateView.as_view()),
    get("/<int:pk>/edit",    PostUpdateView.as_view(), name="post_update"),
    post("/<int:pk>/edit",   PostUpdateView.as_view()),
    get("/<int:pk>/delete",  PostDeleteView.as_view(), name="post_delete"),
    post("/<int:pk>/delete", PostDeleteView.as_view()),
]
```
