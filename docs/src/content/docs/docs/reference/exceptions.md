---
title: "Exceptions"
description: "All Buraq exceptions live in buraq.exceptions and inherit from BuraqException."
---

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

### SuspiciousFileOperation

Subclass of `SuspiciousOperation`. Raised by `FileSystemStorage` when a file
name resolves outside the configured storage root (path traversal attempt):

```python
from buraq.exceptions import SuspiciousFileOperation

try:
    await storage.open("../../etc/passwd")
except SuspiciousFileOperation as e:
    logger.warning("Path traversal blocked: %s", e)
```

You do not normally raise this yourself — `FileSystemStorage` raises it
automatically before any disk access occurs.

## Request / security exceptions

These are raised internally by Buraq and result in specific HTTP error responses. You rarely raise them yourself, but you may need to catch them in middleware or custom exception handlers.

| Exception | HTTP status | Description |
|---|---|---|
| `DisallowedHost` | 400 | `Host` header not in `ALLOWED_HOSTS` |
| `DisallowedRedirect` | 400 | Redirect target is not a safe URL |
| `SuspiciousMultipartForm` | 400 | Malformed multipart upload |
| `TooManyFieldsSent` | 400 | Form POST exceeds `DATA_UPLOAD_MAX_NUMBER_FIELDS` |
| `TooManyFilesSent` | 400 | Multipart upload exceeds `DATA_UPLOAD_MAX_NUMBER_FILES` |
| `RequestDataTooBig` | 400 | Request body exceeds `DATA_UPLOAD_MAX_MEMORY_SIZE` |
| `RequestAborted` | — | Client disconnected before the response was sent |
| `InvalidSessionKey` | — | Session key contains illegal characters |

```python
from buraq.exceptions import DisallowedHost, DisallowedRedirect

# Catch in an exception handler middleware:
try:
    response = await call_next(request)
except DisallowedHost:
    return PlainTextResponse("Bad request", status_code=400)
```

## ORM / framework exceptions

| Exception | When raised |
|---|---|
| `FieldDoesNotExist` | Accessing a field name that doesn't exist on a model |
| `ViewDoesNotExist` | URL resolver cannot find the named view |
| `EmptyResultSet` | A queryset optimisation path produces an empty set |
| `FullResultSet` | A queryset optimisation path matches all rows |
| `AppRegistryNotReady` | App models accessed before `AppConfig.ready()` |
| `MiddlewareNotUsed` | Raised by middleware `__init__` to remove itself from the stack |

```python
from buraq.exceptions import FieldDoesNotExist

try:
    field = MyModel._meta.get_field("nonexistent")
except FieldDoesNotExist:
    ...
```

## Reference

| Exception | Module | When to raise / catch |
|---|---|---|
| `ObjectDoesNotExist` | `buraq.exceptions` | Catch after `get()` |
| `MultipleObjectsReturned` | `buraq.exceptions` | Catch after `get()` |
| `ValidationError` | `buraq.exceptions` | Raise in validators / `clean()` |
| `FieldError` | `buraq.exceptions` | Invalid field names in queries |
| `FieldDoesNotExist` | `buraq.exceptions` | Non-existent model field |
| `PermissionDenied` | `buraq.exceptions` | Access control → 403 |
| `ImproperlyConfigured` | `buraq.exceptions` | Bad settings / startup |
| `SuspiciousOperation` | `buraq.exceptions` | Malicious / malformed input |
| `SuspiciousFileOperation` | `buraq.exceptions` | File name escapes storage root |
| `SuspiciousMultipartForm` | `buraq.exceptions` | Malformed multipart body |
| `DisallowedHost` | `buraq.exceptions` | Invalid Host header |
| `DisallowedRedirect` | `buraq.exceptions` | Unsafe redirect URL |
| `RequestAborted` | `buraq.exceptions` | Client disconnected |
| `TooManyFieldsSent` | `buraq.exceptions` | POST field limit exceeded |
| `TooManyFilesSent` | `buraq.exceptions` | File upload count exceeded |
| `RequestDataTooBig` | `buraq.exceptions` | Body size limit exceeded |
| `InvalidSessionKey` | `buraq.exceptions` | Illegal characters in session key |
| `ViewDoesNotExist` | `buraq.exceptions` | Named view not found |
| `EmptyResultSet` | `buraq.exceptions` | ORM optimisation — empty set |
| `FullResultSet` | `buraq.exceptions` | ORM optimisation — full set |
| `AppRegistryNotReady` | `buraq.exceptions` | Models accessed too early |
| `MiddlewareNotUsed` | `buraq.exceptions` | Middleware self-removal |
| `Http404` | `buraq.http` | Resource not found → 404 |
