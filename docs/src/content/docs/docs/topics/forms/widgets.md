---
title: "Widgets"
description: "A widget controls how a form field is rendered as HTML. Every field has a default widget; you can override it with widget=."
---

A widget controls how a form field is rendered as HTML. Every field has a default widget; you can override it with `widget=`.

## Built-in widgets

| Widget | Default for | Renders |
|---|---|---|
| `TextInput` | `CharField` | `<input type="text">` |
| `PasswordInput` | — | `<input type="password">`, empty on redisplay |
| `Textarea` | `TextField` | `<textarea>` |
| `NumberInput` | `IntegerField`, `FloatField` | `<input type="number">` |
| `URLInput` | `URLField` | `<input type="url">` |
| `DateInput` | `DateField` | `<input type="date">` |
| `DateTimeInput` | `DateTimeField` | `<input type="datetime-local">` |
| `TimeInput` | `TimeField` | `<input type="time">` |
| `CheckboxInput` | `BooleanField` | `<input type="checkbox">` |
| `Select` | `ChoiceField` | `<select>` |
| `RadioSelect` | — | `<ul>` of `<input type="radio">` buttons |
| `NullBooleanSelect` | `NullBooleanField` | `<select>` with Unknown/Yes/No options |
| `CheckboxSelectMultiple` | `MultipleChoiceField` | `<ul>` of `<input type="checkbox">` |
| `MultipleHiddenInput` | — | Multiple `<input type="hidden">` for multi-value fields |
| `FileInput` | `FileField` | `<input type="file">` |
| `ClearableFileInput` | `FileField` (model forms) | File input with a "Clear" checkbox for clearing existing files |
| `HiddenInput` | `HiddenField` | `<input type="hidden">` |
| `MultiWidget` | `SplitDateTimeField` | Combines multiple sub-widgets into one field |
| `SplitDateTimeWidget` | `SplitDateTimeField` | Separate `DateInput` + `TimeInput` combined into a `datetime` |
| `SplitHiddenDateTimeWidget` | — | Hidden version of `SplitDateTimeWidget` |
| `SelectDateWidget` | — | Three `<select>` dropdowns for year, month, day |

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

## Passwords

`PasswordInput` does not put the submitted value back into the HTML when a form
is redisplayed after a validation error — otherwise a failed login would print
the password into the page, where it reaches browser history, caches and any
screenshot of the tab:

```python
fields.CharField(widget=PasswordInput())
# after a failed submit -> <input type="password" name="password" value="">
```

Pass `render_value=True` to keep it, which is worth it only where the value is
not a secret.

## Base classes

Two widgets exist to be subclassed rather than used directly:

| | for | gives the subclass |
|---|---|---|
| `ChoiceWidget` | anything backed by `(value, label)` pairs | a `choices` constructor argument, stored as a list |
| `FormatWidget` | anything that stringifies a date or time | a `format` argument overriding the class default |

```python
from buraq.forms.widgets import ChoiceWidget, FormatWidget


class ButtonSelect(ChoiceWidget):
    def render(self, name, value, attrs=None):
        return "".join(
            f'<button name="{name}" value="{v}">{label}</button>'
            for v, label in self.choices
        )


class ShortDateInput(FormatWidget):
    format = "%d/%m/%Y"
```

`Select`, `RadioSelect` and the other choice widgets derive from the first;
`DateInput`, `TimeInput` and `DateTimeInput` from the second. Passing `format`
to any of those overrides the class default for that one instance:

```python
DateInput(attrs={"type": "date"}, format="%d/%m/%Y")
```
