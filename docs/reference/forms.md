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

## BoundField

Returned when iterating over a form or accessing `form["field_name"]`.

| Attribute | Description |
|---|---|
| `bound.name` | Field name (`"title"`) |
| `bound.html_name` | HTML name attribute (with prefix if set) |
| `bound.label` | Human-readable label |
| `bound.value` | Current value (from data or initial) |
| `bound.errors` | List of error messages for this field |
| `bound.help_text` | Help text string |
| `str(bound)` | String representation of the value |

---

## ValidationError

```python
from buraq.exceptions import ValidationError

raise ValidationError("This field is required.")
raise ValidationError("Value too short.", code="min_length")
```
