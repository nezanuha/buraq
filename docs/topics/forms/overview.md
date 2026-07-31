# Forms Overview

Buraq forms handle HTML form rendering, data validation, and model persistence — identical in design to Django forms.

## Two form types

| | `Form` | `ModelForm` |
|---|---|---|
| Fields | Defined manually | Auto-generated from model columns |
| Save | Manual | `await form.save()` creates/updates the model |
| Use for | Contact forms, search, login | Any form tied to a model |

## Quick example

```python
from buraq.forms import Form, ModelForm
from buraq.forms.fields import CharField, EmailField, TextField
from buraq.exceptions import ValidationError


class ContactForm(Form):
    name    = CharField(max_length=100)
    email   = EmailField()
    message = TextField()

    def clean_message(self, value):
        if len(value) < 10:
            raise ValidationError("Message too short.")
        return value


class PostForm(ModelForm):
    class Meta:
        model  = Post
        fields = ["title", "slug", "content", "is_published"]
```

## In a view

```python
async def contact(request):
    if request.method == "POST":
        form = ContactForm(data=dict(await request.form()))
        if await form.is_valid():
            send_email(form.cleaned_data)
            return redirect("/thanks/")
    else:
        form = ContactForm()

    return render(request, "contact.html", {"form": form})
```

## Validation is always async

```python
if await form.is_valid():     # always await
    data = form.cleaned_data
```

## Accessing data after validation

```python
if await form.is_valid():
    title   = form.cleaned_data["title"]
    content = form.cleaned_data["content"]
```

## Errors

```python
# Field errors
form.errors           # {"title": ["This field is required."]}

# Non-field (cross-field) errors
form.non_field_errors()

# Check for a specific field error
form.has_error("title")
```

## Adding errors manually

```python
async def clean(self):
    data = self._cleaned_data
    if data.get("start") > data.get("end"):
        self.add_error("end", "End date must be after start date.")
    return data
```
