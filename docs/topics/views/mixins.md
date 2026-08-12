# Auth Mixins

Mixin classes add authentication and permission checks to class-based views.

```python
from buraq.views.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
```

---

## LoginRequiredMixin

Redirect unauthenticated users to the login page.

```python
from buraq.views.mixins import LoginRequiredMixin
from buraq.views.generic import DetailView

class PostDetailView(LoginRequiredMixin, DetailView):
    model = Post
    template_name = "posts/detail.html"
```

By default redirects to `/accounts/login/`. Override `login_url` to change:

```python
class PostDetailView(LoginRequiredMixin, DetailView):
    model = Post
    login_url = "/auth/signin/"
```

To return a 403 instead of redirecting:

```python
class PostDetailView(LoginRequiredMixin, DetailView):
    model = Post
    raise_exception = True
```

---

## PermissionRequiredMixin

Require the user to hold a specific permission.

```python
from buraq.views.mixins import PermissionRequiredMixin
from buraq.views.generic import UpdateView

class PostEditView(PermissionRequiredMixin, UpdateView):
    model = Post
    permission_required = "blog.change_post"
    success_url = "/posts/"
```

Require multiple permissions — all must be held:

```python
class PostPublishView(PermissionRequiredMixin, UpdateView):
    model = Post
    permission_required = ["blog.change_post", "blog.publish_post"]
```

Unauthenticated users are redirected to `login_url`. Authenticated users without the permission get a 403 (or redirect, depending on `raise_exception`).

---

## UserPassesTestMixin

Deny access based on a custom condition.

```python
from buraq.views.mixins import UserPassesTestMixin
from buraq.views.generic import DetailView

class StaffOnlyView(UserPassesTestMixin, DetailView):
    model = Post

    async def test_func(self, request) -> bool:
        return request.user.is_staff
```

---

## AccessMixin (base class)

All auth mixins inherit from `AccessMixin`. Override `handle_no_permission()` to customize the denied response:

```python
from starlette.responses import JSONResponse
from buraq.views.mixins import LoginRequiredMixin

class APILoginRequired(LoginRequiredMixin, View):
    async def handle_no_permission(self, request):
        return JSONResponse({"error": "authentication required"}, status_code=401)
```

---

## SuccessMessageMixin

Display a flash success message after a form is successfully submitted. Mix with any `FormView`, `CreateView`, or `UpdateView`.

```python
from buraq.views.mixins import SuccessMessageMixin
from buraq.views.generic import CreateView

class CreatePostView(SuccessMessageMixin, CreateView):
    model = Post
    fields = ["title", "body"]
    success_url = "/posts/"
    success_message = "Post '%(title)s' was created successfully."
```

`success_message` supports `%(field)s` placeholders filled from `form.cleaned_data`.

Override `get_success_message()` for dynamic messages:

```python
class CreatePostView(SuccessMessageMixin, CreateView):
    model = Post
    fields = ["title", "body"]
    success_url = "/posts/"

    def get_success_message(self, cleaned_data: dict) -> str:
        if cleaned_data.get("is_published"):
            return f"Post '{cleaned_data['title']}' published!"
        return f"Post '{cleaned_data['title']}' saved as draft."
```

The message is passed to `buraq.contrib.messages.success(request, msg)` and displayed via the messages framework (add `buraq.middleware.common.MessageMiddleware` to `MIDDLEWARE` and render `{{ messages }}` in your base template).

---

## Mixin order

Always put mixin classes **before** the view class:

```python
# Correct
class MyView(LoginRequiredMixin, PermissionRequiredMixin, DetailView): ...

# Wrong — LoginRequiredMixin won't be called
class MyView(DetailView, LoginRequiredMixin): ...
```
