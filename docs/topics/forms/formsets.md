# Formsets

A formset manages a collection of identical forms — useful for editing multiple model instances in one submission.

## Basic formset

```python
from buraq.forms import Form
from buraq.forms.fields import CharField, IntegerField
from buraq.forms.formsets import formset_factory


class BookForm(Form):
    title  = CharField(max_length=200)
    pages  = IntegerField(min_value=1)


BookFormSet = formset_factory(BookForm, extra=2)
```

In a view:

```python
async def manage_books(request):
    if request.method == "POST":
        formset = BookFormSet(data=dict(await request.form()))
        if await formset.is_valid():
            for form in formset.forms:
                if form.cleaned_data:
                    save_book(form.cleaned_data)
            return redirect("/books")
    else:
        formset = BookFormSet()
    return render(request, "books/manage.html", {"formset": formset})
```

In the template:

```html
<form method="post">
  {{ formset.management_form_html() | safe }}
  {% for form in formset %}
    <div>
      {% for field in form %}
        {{ field.label }}: <input name="{{ field.html_name }}" value="{{ field.value }}">
        {% for error in field.errors %}<span>{{ error }}</span>{% endfor %}
      {% endfor %}
    </div>
  {% endfor %}
  <button type="submit">Save</button>
</form>
```

## formset_factory options

```python
BookFormSet = formset_factory(
    BookForm,
    extra        = 2,          # number of blank extra forms
    can_delete   = True,       # add a DELETE checkbox per form
    can_order    = False,       # add an ORDER field per form
    min_num      = 1,          # minimum filled forms
    max_num      = 10,         # maximum filled forms
    validate_min = True,       # raise error if filled < min_num
    validate_max = True,       # raise error if filled > max_num
)
```

## Model formsets

Edit multiple model instances without writing boilerplate forms.

```python
from buraq.forms.formsets import modelformset_factory

ArticleFormSet = modelformset_factory(
    Article,
    fields = ["title", "body"],
    extra  = 1,
)

async def edit_articles(request):
    if request.method == "POST":
        formset = ArticleFormSet(data=dict(await request.form()))
        if await formset.is_valid():
            await formset.save()
            return redirect("/articles")
    else:
        existing = await Article.objects.filter(is_published=False).all()
        formset  = ArticleFormSet(initial=[
            {"title": a.title, "body": a.body} for a in existing
        ])
    return render(request, "articles/edit.html", {"formset": formset})
```

## Inline formsets

Edit child objects related to a parent via a ForeignKey — the classic "edit post + its comments in one page" pattern.

```python
from buraq.forms.formsets import inlineformset_factory

CommentFormSet = inlineformset_factory(
    Post,            # parent model
    Comment,         # child model
    fk_field = "post_id",   # FK column on Comment; auto-detected if omitted
    fields   = ["body", "author"],
    extra    = 3,
    can_delete = True,
)

async def edit_post(request, pk: int):
    post = await get_object_or_404(Post, id=pk)

    if request.method == "POST":
        formset = CommentFormSet(data=dict(await request.form()))
        formset.parent_instance = post
        if await formset.is_valid():
            await formset.save()
            return redirect(f"/posts/{pk}")
    else:
        comments = await Comment.objects.filter(post_id=pk).all()
        formset = CommentFormSet(
            initial=[{"body": c.body, "author": c.author} for c in comments],
        )
        formset.parent_instance = post

    return render(request, "posts/edit.html", {"post": post, "formset": formset})
```

## Cross-formset validation

Override `clean()` to add validation that spans multiple forms:

```python
from buraq.exceptions import ValidationError
from buraq.forms.formsets import BaseFormSet, formset_factory


class UniqueEmailFormSet(BaseFormSet):
    async def clean(self):
        emails = []
        for form in self.forms:
            email = form.cleaned_data.get("email")
            if email in emails:
                raise ValidationError("Each email must be unique.")
            emails.append(email)


EmailFormSet = formset_factory(EmailForm, formset=UniqueEmailFormSet)
```

## FormSet API reference

| Property / Method | Description |
|---|---|
| `formset.forms` | List of all form instances |
| `formset.initial_forms` | Forms pre-populated from `initial` |
| `formset.extra_forms` | Blank extra forms |
| `await formset.is_valid()` | Validate all forms; returns `True`/`False` |
| `formset.cleaned_data()` | List of `cleaned_data` dicts for non-empty valid forms |
| `formset.errors` | List of error dicts, one per form |
| `formset.non_form_errors()` | Cross-formset errors from `clean()` |
| `formset.management_form_html()` | HTML string of hidden management fields |
| `await formset.save()` | *(ModelFormSet only)* Save all valid instances |
