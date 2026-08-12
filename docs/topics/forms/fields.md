# Form Fields

## All built-in fields

| Field | Description |
|---|---|
| `CharField` | Single-line text |
| `TextField` | Multi-line text (renders as `<textarea>`) |
| `PasswordField` | Masked text input |
| `HiddenField` | Hidden input |
| `IntegerField` | Whole numbers |
| `FloatField` | Floating point numbers |
| `DecimalField` | Fixed-precision decimals |
| `BooleanField` | True/False |
| `NullBooleanField` | True/False/None |
| `EmailField` | Valid email address |
| `URLField` | Valid URL |
| `SlugField` | Slug (letters, numbers, hyphens, underscores) |
| `IPAddressField` | IPv4 or IPv6 address |
| `GenericIPAddressField` | IPv4 or IPv6 address |
| `UUIDField` | UUID |
| `DateField` | Date (YYYY-MM-DD) |
| `DateTimeField` | Date and time |
| `TimeField` | Time (HH:MM or HH:MM:SS) |
| `ChoiceField` | Select from a list |
| `MultipleChoiceField` | Select multiple from a list |
| `TypedChoiceField` | `ChoiceField` with type coercion |
| `TypedMultipleChoiceField` | `MultipleChoiceField` with type coercion |
| `ModelChoiceField` | Select a single model instance from a queryset |
| `ModelMultipleChoiceField` | Select multiple model instances from a queryset |
| `FileField` | File upload |
| `ImageField` | Image upload (validates content type) |
| `JSONField` | JSON data |
| `RegexField` | Text matching a regex pattern |
| `SplitDateTimeField` | Separate date + time inputs combined into a `datetime` |
| `MultiValueField` | Combines several fields into one; override `compress()` to merge values |
| `ComboField` | Runs a single value through multiple validators in sequence |

## Common options

All fields accept:

```python
CharField(
    required      = True,         # field is required (default: True)
    label         = "Title",      # human-readable label
    initial       = "",           # default value when form is unbound
    help_text     = "Max 200 chars",
    error_messages = {"required": "Please enter a title."},
    validators    = [my_validator],
    disabled      = False,
)
```

## CharField

```python
CharField(
    max_length  = 200,   # max character length
    min_length  = 3,     # min character length
    strip       = True,  # strip whitespace (default: True)
    empty_value = "",    # value returned for empty input
)
```

## IntegerField / FloatField / DecimalField

```python
IntegerField(min_value=0, max_value=100)
FloatField(min_value=0.0, max_value=1.0)
DecimalField(max_digits=10, decimal_places=2, min_value=0, max_value=9999.99)
```

## ChoiceField

```python
SIZES = [("s", "Small"), ("m", "Medium"), ("l", "Large")]

size = ChoiceField(choices=SIZES)
```

## DateField

```python
DateField(
    input_formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"],  # accepted parse formats
    required      = True,
)
```

`to_python()` tries each format in order; raises `ValidationError` if none match.

## RegexField

```python
phone = RegexField(regex=r"^\+?1?\d{9,15}$", label="Phone number")
```

## ModelChoiceField

Select a single model instance from a queryset. The field validates and stores the primary key; use `fetch()` to retrieve the actual object.

```python
from buraq.forms import ModelChoiceField

class PostForm(Form):
    author = ModelChoiceField(
        queryset    = User.objects.filter(is_active=True),
        empty_label = "— Select author —",
        required    = True,
    )

# In your view — after form.is_valid():
author = await form.fields["author"].fetch(form.cleaned_data["author"])
```

## ModelMultipleChoiceField

Select multiple model instances from a queryset.

```python
from buraq.forms import ModelMultipleChoiceField

class PostForm(Form):
    tags = ModelMultipleChoiceField(
        queryset = Tag.objects.all(),
        required = False,
    )

# Fetch selected instances
tags = await form.fields["tags"].fetch_many(form.cleaned_data["tags"])
```

## TypedChoiceField / TypedMultipleChoiceField

Coerce the submitted string value to a Python type.

```python
from buraq.forms import TypedChoiceField, TypedMultipleChoiceField

priority = TypedChoiceField(
    choices   = [(1, "Low"), (2, "Medium"), (3, "High")],
    coerce    = int,
    empty_value = None,
)

levels = TypedMultipleChoiceField(
    choices = [(1, "One"), (2, "Two"), (3, "Three")],
    coerce  = int,
)
```

## SplitDateTimeField

Accepts a two-element list `[date_string, time_string]` from a form that uses two separate inputs, and combines them into a single `datetime.datetime`.

```python
from buraq.forms.fields import SplitDateTimeField

class EventForm(Form):
    starts_at = SplitDateTimeField()
```

```html+jinja
<input name="starts_at_0" type="date">
<input name="starts_at_1" type="time">
```

The date is parsed with `DateField`'s formats and the time with `TimeField`'s formats. `compress([date, time])` returns `datetime.combine(date, time)`.

## FilePathField

Select a file from a directory on disk. Choices are populated at class-creation time by scanning the directory.

```python
from buraq.forms.fields import FilePathField

class UploadForm(Form):
    template = FilePathField(path="/srv/templates", match=r".*\.html$", recursive=False)
```

### set_choices()

In long-running processes (e.g. ASGI servers that never restart) the directory may change after the field is instantiated. Call `set_choices()` to force a fresh scan:

```python
form_instance.fields["template"].set_choices()
```

This is also useful if you store `FilePathField` instances at module level and need to refresh them per request.

## Custom validators

```python
from buraq.exceptions import ValidationError


def validate_no_profanity(value):
    if "badword" in value.lower():
        raise ValidationError("Profanity is not allowed.")


name = CharField(validators=[validate_no_profanity])
```
