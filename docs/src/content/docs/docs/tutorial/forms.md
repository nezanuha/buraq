---
title: "Part 3 — Forms"
description: "Build forms in Buraq with plain Form and ModelForm classes — wiring them into views, rendering them in templates, and understanding the validation flow."
---

## Plain Form

```python title="posts/forms.py"
from buraq.forms import Form
from buraq.forms.fields import CharField, TextField, EmailField
from buraq.exceptions import ValidationError


class CommentForm(Form):
    author_name = CharField(max_length=100, label="Your name")
    email       = EmailField(required=False, label="Email (optional)")
    body        = TextField(label="Comment")

    def clean_body(self, value):
        if len(value.strip()) < 5:
            raise ValidationError("Comment must be at least 5 characters.")
        return value.strip()
```

## ModelForm

Auto-generates fields from model columns:

```python title="posts/forms.py"
from buraq.forms import ModelForm
from buraq.exceptions import ValidationError
from posts.models import Post


class PostForm(ModelForm):
    class Meta:
        model  = Post
        fields = ["title", "slug", "content", "is_published"]

    def clean_slug(self, value):
        if " " in value:
            raise ValidationError("Slug must not contain spaces.")
        return value.lower()

    async def clean(self):
        data = self._cleaned_data
        if data.get("is_published") and not data.get("content"):
            self.add_error("content", "Cannot publish without content.")
        return data
```

## Using forms in views

```python title="posts/views.py"
from buraq.shortcuts import render, redirect
from posts.forms import CommentForm, PostForm
from posts.models import Post


async def create_post(request):
    if request.method == "POST":
        form = PostForm(data=dict(await request.form()))
        if await form.is_valid():
            post = await form.save()
            return redirect(f"/posts/{post.slug}")
    else:
        form = PostForm()

    return await render(request, "posts/form.html", {"form": form})


async def edit_post(request, pk: int):
    post = await Post.objects.get(id=pk)
    if request.method == "POST":
        form = PostForm(data=dict(await request.form()), instance=post)
        if await form.is_valid():
            await form.save()
            return redirect(f"/posts/{post.slug}")
    else:
        form = PostForm(instance=post)   # pre-fills fields from instance

    return await render(request, "posts/form.html", {"form": form})
```

## Rendering forms in templates

```html+jinja title="templates/posts/form.html"
<form method="post">
  {% for field in form %}
    <div class="field">
      <label for="{{ field.html_name }}">{{ field.label }}</label>

      {% if field.errors %}
        {% for err in field.errors %}
          <p class="error">{{ err }}</p>
        {% endfor %}
      {% endif %}

      <input type="text"
             name="{{ field.html_name }}"
             id="{{ field.html_name }}"
             value="{{ field.value }}">
    </div>
  {% endfor %}

  <button type="submit">Save</button>
</form>
```

## Validation flow

1. `field.clean(raw_value)` — converts type, checks required, runs field validators
2. `form.clean_<fieldname>(value)` — per-field custom validation
3. `form.clean()` — cross-field validation (can be `async def`)

Next: [Templates →](templates.md)
