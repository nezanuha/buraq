# Exceptions

All Buraq exceptions live in `buraq.exceptions` and inherit from `BuraqException`.

## ORM exceptions

### ObjectDoesNotExist

Raised by `QuerySet.get()` when no row matches the filter.

```python
from buraq.exceptions import ObjectDoesNotExist

try:
    post = await Post.objects.get(id=999)
except ObjectDoesNotExist:
    raise Http404("Post not found")
```

Each model also exposes a model-specific subclass: `Post.DoesNotExist`.

### MultipleObjectsReturned

Raised by `QuerySet.get()` when more than one row matches.

```python
from buraq.exceptions import MultipleObjectsReturned

try:
    user = await User.objects.get(email=email)
except MultipleObjectsReturned:
    # duplicate accounts — handle accordingly
    ...
```

## Validation

### ValidationError

Raised by form fields, validators, and model `clean()` methods.

```python
from buraq.exceptions import ValidationError

def validate_positive(value):
    if value <= 0:
        raise ValidationError("Must be a positive number.", code="invalid")
```

Accepts a `code` (machine-readable slug) and `params` (for interpolation):

```python
raise ValidationError("Value %(value)s is too large.", code="max_value", params={"value": val})
```

`NON_FIELD_ERRORS = "__all__"` is the sentinel key used in `form.errors` for form-level errors that don't belong to a specific field.

### FieldError

Raised when an invalid field name or lookup is used in a queryset.

```python
from buraq.exceptions import FieldError
```

## Access control

### PermissionDenied

Raise to return a 403 response. Buraq registers an exception handler automatically.

```python
from buraq.exceptions import PermissionDenied

async def admin_view(request):
    if not request.user.is_staff:
        raise PermissionDenied("Staff access required.")
```

## Configuration

### ImproperlyConfigured

Raise during startup when required settings or app configuration are missing.

```python
from buraq.exceptions import ImproperlyConfigured

if not settings.SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY must be set.")
```

### SuspiciousOperation

Raise when a request contains data that appears to be malicious or malformed — e.g. a tampered cookie or an invalid redirect target.

```python
from buraq.exceptions import SuspiciousOperation

if not url_has_allowed_host_and_scheme(next_url, allowed_hosts=ALLOWED_HOSTS):
    raise SuspiciousOperation("Unsafe redirect target.")
```

## Reference

| Exception | Module | When to raise / catch |
|---|---|---|
| `ObjectDoesNotExist` | `buraq.exceptions` | Catch after `get()` |
| `MultipleObjectsReturned` | `buraq.exceptions` | Catch after `get()` |
| `ValidationError` | `buraq.exceptions` | Raise in validators / `clean()` |
| `FieldError` | `buraq.exceptions` | Invalid field names in queries |
| `PermissionDenied` | `buraq.exceptions` | Access control → 403 |
| `ImproperlyConfigured` | `buraq.exceptions` | Bad settings / startup |
| `SuspiciousOperation` | `buraq.exceptions` | Malicious / malformed input |
| `Http404` | `buraq.http` | Resource not found → 404 |
