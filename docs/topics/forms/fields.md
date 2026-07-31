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
| `FileField` | File upload |
| `ImageField` | Image upload (validates content type) |
| `JSONField` | JSON data |
| `RegexField` | Text matching a regex pattern |

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

## RegexField

```python
phone = RegexField(regex=r"^\+?1?\d{9,15}$", label="Phone number")
```

## Custom validators

```python
from buraq.exceptions import ValidationError


def validate_no_profanity(value):
    if "badword" in value.lower():
        raise ValidationError("Profanity is not allowed.")


name = CharField(validators=[validate_no_profanity])
```
