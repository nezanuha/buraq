# System Checks

`buraq.checks` validates your configuration at startup, catching common misconfigurations before they cause runtime errors.

## Built-in checks

Buraq runs these automatically on startup:

| ID | Level | Description |
|---|---|---|
| `security.E001` | Error | `SECRET_KEY` is the insecure default |
| `security.W001` | Warning | `SECRET_KEY` is shorter than 50 characters |
| `security.W002` | Warning | `DEBUG=True` with `ALLOWED_HOSTS=["*"]` |
| `database.W001` | Warning | SQLite configured without `DEBUG=True` |

## Running checks manually

```python
from buraq.checks import run_checks

messages = run_checks()
for msg in messages:
    print(f"[{msg.__class__.__name__}] {msg.id}: {msg}")
```

## Startup behaviour

On application startup, Buraq calls `registry.run_checks_or_raise()`. If any
check emits an **Error**-level (or higher) message **and** `DEBUG=False`, an
`ImproperlyConfigured` exception is raised immediately, preventing the app from
serving requests in a broken state:

```
buraq.exceptions.ImproperlyConfigured: System check found 1 error(s): ...
```

In `DEBUG=True` mode, errors are printed as warnings but do not abort startup,
so development servers remain usable even with misconfigured optional features.

## Writing custom checks

```python
from buraq.checks import register, Error, Warning

@register
def check_api_key(settings, **kwargs):
    errors = []
    if not getattr(settings, "STRIPE_API_KEY", None):
        errors.append(Warning(
            "STRIPE_API_KEY is not configured.",
            hint="Set STRIPE_API_KEY in your .env file.",
            id="payments.W001",
        ))
    return errors
```

Register it anywhere that's imported at startup (e.g. your `AppConfig.ready()`).

## Message levels

| Class | Level | When to use |
|---|---|---|
| `Debug` | 10 | Developer info, never shown in production |
| `Info` | 20 | Non-critical notes |
| `Warning` | 30 | Something is wrong but the app can start |
| `Error` | 40 | Configuration is broken — app may malfunction |
| `Critical` | 50 | App cannot function at all |

## CheckMessage attributes

```python
msg.msg     # Human-readable description
msg.hint    # Optional suggestion to fix the problem
msg.id      # Dot-separated identifier, e.g. "security.E001"
msg.obj     # Optional object that triggered the check
```
