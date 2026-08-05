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

## FormView

Handle a form's GET/POST cycle without tying it to a model. See [FormView](form-view.md) for the full reference.

```python
from buraq.views.generic import FormView

class ContactView(FormView):
    template_name = "contact.html"
    form_class    = ContactForm
    success_url   = "/thanks/"

    async def form_valid(self, request, form):
        await send_contact_email(form.cleaned_data)
        return redirect(self.success_url)
```

---

## Date archive views

Filter objects by date field. All archive views share `date_field` (default `"created_at"`) and `allow_future`.

```python
from buraq.views.generic import (
    YearArchiveView, MonthArchiveView, WeekArchiveView,
    DayArchiveView, TodayArchiveView, ArchiveIndexView, DateDetailView,
)
```

### YearArchiveView / MonthArchiveView

```python
class PostYearView(YearArchiveView):
    model      = Post
    date_field = "published_on"

class PostMonthView(MonthArchiveView):
    model      = Post
    date_field = "published_on"

urlpatterns = [
    get("/<int:year>",         PostYearView.as_view()),
    get("/<int:year>/<int:month>", PostMonthView.as_view()),
]
```

### WeekArchiveView

List objects for an ISO week number.

```python
class PostWeekView(WeekArchiveView):
    model      = Post
    date_field = "published_on"

# URL: /2024/week/12
get("/<int:year>/week/<int:week>", PostWeekView.as_view())
```

### DayArchiveView

```python
class PostDayView(DayArchiveView):
    model      = Post
    date_field = "published_on"

# URL: /2024/3/15
get("/<int:year>/<int:month>/<int:day>", PostDayView.as_view())
```

### TodayArchiveView

No URL parameters needed — always uses today's date.

```python
class TodayPostsView(TodayArchiveView):
    model      = Post
    date_field = "published_on"

get("/today", TodayPostsView.as_view())
```

### ArchiveIndexView

Top-level archive — provides a list of all distinct years in `date_list`.

```python
class PostArchiveView(ArchiveIndexView):
    model      = Post
    date_field = "published_on"
    template_name = "posts/archive.html"
    # context: date_list (list of year dates)

get("/archive", PostArchiveView.as_view())
```

### DateDetailView

Retrieve a single object by year/month/day + pk or slug.

```python
class PostDateDetailView(DateDetailView):
    model      = Post
    date_field = "published_on"
    template_name = "posts/detail.html"

get("/<int:year>/<int:month>/<int:day>/<int:pk>", PostDateDetailView.as_view())
```

---

## Auth mixins

Add access control to any CBV by mixing in before the view class. See [Auth Mixins](mixins.md) for the full reference.

```python
from buraq.views.mixins import LoginRequiredMixin, PermissionRequiredMixin

class PostCreateView(LoginRequiredMixin, CreateView):
    model      = Post
    form_class = PostForm
    success_url = "/posts/"

class PostPublishView(PermissionRequiredMixin, UpdateView):
    model               = Post
    permission_required = "blog.publish_post"
    success_url         = "/posts/"
```

---

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
