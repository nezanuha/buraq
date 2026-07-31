# buraq.views — API Reference

## View

```python
from buraq.views import View
```

Base class for all class-based views.

### Class attributes

| Attribute | Default | Description |
|---|---|---|
| `http_method_names` | all methods | Allowed HTTP methods |

### Methods

| Method | Description |
|---|---|
| `View.as_view(**initkwargs)` | Returns an async function for URL registration |
| `await self.dispatch(request, **kwargs)` | Routes to the correct method handler |
| `await self.http_method_not_allowed(request)` | Returns 405 |
| `await self.options(request)` | Returns 200 with `Allow` header |

---

## Generic Views

### TemplateView

```python
from buraq.views.generic import TemplateView

class HomeView(TemplateView):
    template_name = "home.html"
    extra_context = {"title": "Home"}
```

### ListView

```python
class PostListView(ListView):
    model         = Post           # required (or override get_queryset)
    template_name = "list.html"
    paginate_by   = None           # int to enable pagination
    ordering      = None           # list of field names
    page_kwarg    = "page"         # query param name for page number
    allow_empty   = True           # allow empty list (default: True)
```

Template context: `object_list`, `<model_name>_list`, `paginator`, `page_obj`, `is_paginated`

### DetailView

```python
class PostDetailView(DetailView):
    model            = Post
    template_name    = "detail.html"
    pk_url_kwarg     = "pk"        # URL param name
    slug_url_kwarg   = "slug"
    slug_field       = "slug"      # model field to match slug against
    context_object_name = None     # override default (model name lowercased)
```

Template context: `object`, `<model_name>`

### CreateView

```python
class PostCreateView(CreateView):
    model         = Post
    form_class    = PostForm       # required
    template_name = "form.html"
    success_url   = "/posts/"      # required
```

### UpdateView

```python
class PostUpdateView(UpdateView):
    model         = Post
    form_class    = PostForm
    template_name = "form.html"
    success_url   = "/posts/"
    pk_url_kwarg  = "pk"
```

### DeleteView

```python
class PostDeleteView(DeleteView):
    model         = Post
    template_name = "confirm_delete.html"
    success_url   = "/posts/"
```

### RedirectView

```python
class OldUrlRedirect(RedirectView):
    url       = "/new-url/"
    permanent = False    # 302 (True = 301)
```

---

## Mixins

| Mixin | Provides |
|---|---|
| `ContextMixin` | `async get_context_data(**kwargs)` |
| `TemplateMixin` | `get_template_name()` |
| `SingleObjectMixin` | `async get_object()`, `get_context_object_name()` |
| `MultipleObjectMixin` | `async get_queryset()`, `async paginate_queryset()` |
| `FormMixin` | `get_form()`, `get_initial()`, `get_success_url()`, `async form_valid()`, `async form_invalid()` |
