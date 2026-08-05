# Validators

Validators are callables that raise `ValidationError` when a value is invalid.  They can be attached to model fields or form fields.

## Using validators

```python
from buraq.forms import Form
from buraq.forms.fields import CharField, IntegerField
from buraq.validators import MinLengthValidator, MaxValueValidator, RegexValidator


class SignupForm(Form):
    username = CharField(max_length=150, validators=[MinLengthValidator(3)])
    age      = IntegerField(validators=[MaxValueValidator(120)])
    phone    = CharField(validators=[RegexValidator(r"^\+?1?\d{9,15}$")])
```

## Built-in validators

### MaxLengthValidator / MinLengthValidator

```python
from buraq.validators import MaxLengthValidator, MinLengthValidator

MaxLengthValidator(200)   # value must be ≤ 200 characters
MinLengthValidator(3)     # value must be ≥ 3 characters
```

### MaxValueValidator / MinValueValidator

```python
from buraq.validators import MaxValueValidator, MinValueValidator

MaxValueValidator(100)    # numeric value must be ≤ 100
MinValueValidator(0)      # numeric value must be ≥ 0
```

### RegexValidator

```python
from buraq.validators import RegexValidator

phone = RegexValidator(
    regex   = r"^\+?1?\d{9,15}$",
    message = "Enter a valid phone number.",
    code    = "invalid_phone",
)

# inverse_match=True — passes only when the value does NOT match
no_spaces = RegexValidator(r"\s", inverse_match=True, message="Spaces are not allowed.")
```

### EmailValidator

```python
from buraq.validators import EmailValidator, validate_email

validate_email("alice@example.com")   # OK
validate_email("not-an-email")        # raises ValidationError
```

### URLValidator

```python
from buraq.validators import URLValidator, validate_url

validate_url("https://example.com")  # OK
validate_url("not a url")            # raises ValidationError
```

### SlugValidator / UnicodeSlugValidator

```python
from buraq.validators import SlugValidator, UnicodeSlugValidator

SlugValidator()         # letters, numbers, hyphens, underscores
UnicodeSlugValidator()  # same but allows unicode letters
```

### DecimalValidator

```python
from buraq.validators import DecimalValidator

v = DecimalValidator(max_digits=8, decimal_places=2)
v("12345.99")   # OK
v("123456.789") # raises ValidationError — too many decimal places
```

### validate_integer

```python
from buraq.validators import validate_integer

validate_integer("42")    # OK
validate_integer("abc")   # raises ValidationError
```

### validate_ipv4_address / validate_ipv6_address / validate_ipv46_address

```python
from buraq.validators import validate_ipv4_address, validate_ipv6_address, validate_ipv46_address

validate_ipv4_address("192.168.1.1")   # OK
validate_ipv6_address("::1")           # OK
validate_ipv46_address("10.0.0.1")     # OK — accepts both v4 and v6
```

### FileExtensionValidator

```python
from buraq.validators import FileExtensionValidator

v = FileExtensionValidator(allowed_extensions=["pdf", "docx"])
v(upload_file)   # raises ValidationError if not .pdf or .docx
```

### validate_image_file_extension

```python
from buraq.validators import validate_image_file_extension

# Accepts: .png, .jpg, .gif, .webp, .svg, .bmp, .tiff, .ico, .avif, .apng
validate_image_file_extension(upload_file)
```

### StepValueValidator

```python
from buraq.validators import StepValueValidator

v = StepValueValidator(step=5)
v(10)  # OK
v(11)  # raises ValidationError — not a multiple of 5

# With offset
v2 = StepValueValidator(step=2, offset=1)
v2(3)  # OK (3-1=2, multiple of 2)
```

### ProhibitNullCharactersValidator

```python
from buraq.validators import ProhibitNullCharactersValidator

v = ProhibitNullCharactersValidator()
v("hello\x00world")  # raises ValidationError
```

### BaseValidator

Base class for limit-value validators.  Subclass and override `compare` and `clean`:

```python
from buraq.validators import BaseValidator

class EvenValueValidator(BaseValidator):
    message = "Value must be even (got %(show_value)s)."
    code    = "not_even"

    def compare(self, value, limit):
        return value % 2 != 0

    def clean(self, value):
        return int(value)
```

### int_list_validator

```python
from buraq.validators import int_list_validator

v = int_list_validator(sep=",", allow_negative=False)
v("1,2,3")    # OK
v("1,-2,3")   # raises ValidationError — negatives not allowed
v("1,abc,3")  # raises ValidationError — not an integer
```

## Writing custom validators

```python
from buraq.exceptions import ValidationError


def validate_no_profanity(value: str) -> None:
    if "badword" in value.lower():
        raise ValidationError("Profanity is not allowed.", code="profanity")
```

Attach to a form field:

```python
from buraq.forms.fields import CharField

name = CharField(validators=[validate_no_profanity])
```

## Convenience singletons

```python
from buraq.validators import validate_email, validate_slug, validate_unicode_slug, validate_url
```
