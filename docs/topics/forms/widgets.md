# Widgets

A widget controls how a form field is rendered as HTML. Every field has a default widget; you can override it with `widget=`.

## Built-in widgets

| Widget | Default for | Renders |
|---|---|---|
| `TextInput` | `CharField` | `<input type="text">` |
| `Textarea` | `TextField` | `<textarea>` |
| `NumberInput` | `IntegerField`, `FloatField` | `<input type="number">` |
| `URLInput` | `URLField` | `<input type="url">` |
| `DateInput` | `DateField` | `<input type="date">` |
| `CheckboxInput` | `BooleanField` | `<input type="checkbox">` |
| `Select` | `ChoiceField` | `<select>` |
| `FileInput` | `FileField` | `<input type="file">` |
| `HiddenInput` | `HiddenField` | `<input type="hidden">` |

## Overriding a widget

```python
from buraq.forms import forms, fields
from buraq.forms.widgets import Textarea, Select

class PostForm(forms.Form):
    title   = fields.CharField(max_length=200)
    content = fields.CharField(widget=Textarea)
    status  = fields.ChoiceField(
        choices=[("draft", "Draft"), ("published", "Published")],
        widget=Select,
    )
```

## Widget attributes

Pass HTML attributes via the `attrs` dict:

```python
fields.CharField(widget=TextInput(attrs={"class": "form-control", "placeholder": "Title"}))
```

## Rendering a widget manually

```python
from buraq.forms.widgets import TextInput

widget = TextInput(attrs={"class": "form-input"})
html = widget.render("title", "Hello")
# → '<input type="text" name="title" value="Hello" class="form-input">'
```
