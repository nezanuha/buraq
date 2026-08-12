# buraq.forms — API Reference

## Form

```python
from buraq.forms import Form
```

### Constructor

```python
Form(data=None, files=None, initial=None, prefix=None)
```

| Param | Description |
|---|---|
| `data` | Dict of submitted form data (from `await request.form()`) |
| `initial` | Dict of initial values for unbound form display |
| `prefix` | String prefix for field names (useful for multiple forms on one page) |

### Methods

| Method | Description |
|---|---|
| `await form.is_valid()` | Run validation. Returns `True` if no errors. |
| `form.add_error(field, message)` | Add an error to a field (`None` for non-field errors) |
| `form.non_field_errors()` | List of errors not tied to a specific field |
| `form.has_error(field)` | Check if a field has errors |
| `form.as_p()` | Render form as `<p>` blocks with label, widget, and errors |
| `form.as_table()` | Render form as `<tr>` rows (wrap in `<table>` yourself) |
| `form.as_div()` | Render form as `<div class="form-group">` blocks |
| `form.as_ul()` | Render form as `<li>` items (wrap in `<ul>` yourself) |

### Properties

| Property | Description |
|---|---|
| `form.cleaned_data` | Dict of validated, cleaned values (only after `is_valid()`) |
| `form.errors` | Dict of field errors `{"field": ["message", ...]}` |
| `form.fields` | Dict of field instances |
| `form.data` | Raw submitted data |

### Iteration

```python
for bound_field in form:
    print(bound_field.name, bound_field.value, bound_field.errors)
```

---

## ModelForm

```python
from buraq.forms import ModelForm
```

Inherits all `Form` methods. Additional:

### Constructor

```python
ModelForm(data=None, instance=None, **kwargs)
```

| Param | Description |
|---|---|
| `instance` | Model instance to pre-fill and update on save |

### Methods

| Method | Description |
|---|---|
| `await form.save(commit=True)` | Create or update the model instance |

---

---

## BaseFormSet

```python
from buraq.forms.forms import BaseFormSet
```

Manages a collection of same-type forms.

| Property / Method | Description |
|---|---|
| `formset.forms` | All form instances |
| `formset.initial_forms` | Forms pre-filled from `initial` |
| `formset.extra_forms` | Blank extra forms |
| `await formset.is_valid()` | Validate all forms; returns `True`/`False` |
| `formset.cleaned_data` | List of `cleaned_data` dicts for non-empty valid forms (property) |
| `formset.errors` | List of error dicts, one per form |
| `formset.non_form_errors()` | Cross-formset errors from `clean()` |
| `formset.management_form_html()` | HTML string of hidden management fields |
| `await formset.save()` | *(ModelFormSet only)* Save all valid instances |

## modelformset_factory

```python
from buraq.forms.forms import modelformset_factory

ArticleFormSet = modelformset_factory(
    model   = Article,
    form    = ArticleForm,   # optional; auto-generated if omitted
    extra   = 1,
    max_num = None,
)
```

Returns a `BaseFormSet` subclass that creates/updates multiple instances of `model`.

## inlineformset_factory

```python
from buraq.forms.forms import inlineformset_factory

CommentFormSet = inlineformset_factory(
    parent_model = Post,
    model        = Comment,
    form         = CommentForm,   # optional
    fk_name      = "post_id",     # FK column on child; auto-detected if omitted
    extra        = 3,
    max_num      = None,
)
```

Returns a `BaseFormSet` subclass bound to a parent instance. Set `formset.parent_instance` before calling `save()`.

---

## BoundField

Returned when iterating over a form or accessing `form["field_name"]`.

| Attribute / Method | Description |
|---|---|
| `bound.name` | Field name (`"title"`) |
| `bound.html_name` | HTML name attribute (with prefix if set) |
| `bound.label` | Human-readable label |
| `bound.value` | Current value (from data or initial) |
| `bound.errors` | List of error messages for this field |
| `bound.help_text` | Help text string |
| `bound.label_tag(contents=None, attrs=None)` | Returns `<label for="…">` HTML; `contents` overrides the label text |
| `bound.css_classes(extra_classes="")` | Space-joined CSS class string for the field wrapper |
| `str(bound)` | String representation of the value |

---

## ErrorList / ErrorDict

`form.errors` returns an `ErrorDict` (keyed by field name); each value is an `ErrorList`.

```python
# Render all errors as a UL
print(form.errors.as_ul())

# Access per-field errors
title_errors = form.errors["title"]   # ErrorList
print(title_errors.as_ul())           # <ul class="errorlist"><li>…</li></ul>
```

Both `ErrorList` and `ErrorDict` subclass `list` / `dict` and are JSON-serializable.

---

## ValidationError

```python
from buraq.exceptions import ValidationError

raise ValidationError("This field is required.")
raise ValidationError("Value too short.", code="min_length")
```

---

## Auth Forms

`buraq.contrib.auth.forms` provides ready-to-use forms for login, registration, and password management.

```python
from buraq.contrib.auth.forms import (
    AuthenticationForm,
    BaseUserCreationForm,
    SetPasswordForm,
    PasswordChangeForm,
    AdminPasswordChangeForm,
)
```

### AuthenticationForm

Validates `username` and `password`. Call `await form.get_user(request)` after `is_valid()` to authenticate:

```python
form = AuthenticationForm(await request.form())
if form.is_valid():
    user = await form.get_user(request)
    if user:
        await login(request, user)
        return redirect("/")
```

| Field | Required |
|---|---|
| `username` | Yes |
| `password` | Yes |

### BaseUserCreationForm

Validates `username`, `password1`, and `password2` (must match). Call `await form.save()` to create the user:

```python
form = BaseUserCreationForm(await request.form())
if form.is_valid():
    user = await form.save()
```

Subclass and override `save()` to add extra fields or custom logic.

### SetPasswordForm

Set a new password for a known user (no old-password check — used in password-reset flows):

```python
form = SetPasswordForm(user, await request.form())
if form.is_valid():
    await form.save()
```

| Field | Description |
|---|---|
| `new_password1` | New password |
| `new_password2` | Confirmation (must match) |

### PasswordChangeForm

Like `SetPasswordForm` but also validates the current password:

```python
form = PasswordChangeForm(request.user, await request.form())
if form.is_valid():
    await form.save()
```

| Field | Description |
|---|---|
| `old_password` | Current password (must be correct) |
| `new_password1` | New password |
| `new_password2` | Confirmation |

### AdminPasswordChangeForm

Set any user's password without knowing the current one — for admin/staff flows:

```python
form = AdminPasswordChangeForm(target_user, await request.form())
if form.is_valid():
    await form.save()
```
