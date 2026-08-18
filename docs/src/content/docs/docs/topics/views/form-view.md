---
title: "FormView"
description: "FormView handles the GET/POST cycle for a single form — display the form on GET, validate and redirect on POST."
---

`FormView` handles the GET/POST cycle for a single form — display the form on GET, validate and redirect on POST.

```python
from buraq.views.generic import FormView
```

## Basic usage

```python
class ContactView(FormView):
    template_name = "contact.html"
    form_class    = ContactForm
    success_url   = "/thanks/"
```

Register both GET and POST routes to the same view:

```python
from buraq.urls import path

urlpatterns = [
    path("/contact", ContactView.as_view(), name="contact"),
]
```

## Custom form handling

Override `form_valid()` to process the form data before redirecting:

```python
class ContactView(FormView):
    template_name = "contact.html"
    form_class    = ContactForm
    success_url   = "/thanks/"

    async def form_valid(self, request, form):
        await send_contact_email(form.cleaned_data)
        return redirect(self.success_url)
```

Override `form_invalid()` to customize the error response:

```python
    async def form_invalid(self, request, form):
        ctx = await self.get_context_data(form=form, error="Please fix the errors below.")
        return await render(request, self.get_template_name(), ctx)
```

## Adding context

```python
class ContactView(FormView):
    template_name = "contact.html"
    form_class    = ContactForm
    success_url   = "/thanks/"

    async def get_context_data(self, **kwargs) -> dict:
        ctx = await super().get_context_data(**kwargs)
        ctx["page_title"] = "Contact Us"
        return ctx
```

## With auth mixins

```python
from buraq.views.mixins import LoginRequiredMixin

class PrivateFormView(LoginRequiredMixin, FormView):
    template_name = "private_form.html"
    form_class    = MyForm
    success_url   = "/done/"
```

## FormView vs CreateView

- **`FormView`** — generic form handling; you control what happens on submit.
- **`CreateView`** — specifically creates a model instance from a `ModelForm`.

Use `FormView` for contact forms, search forms, multi-step wizards, or any form not directly tied to a single model.
