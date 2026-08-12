# Signals

Signals let decoupled parts of the application react to events. Identical in design to Django signals.

## Built-in signals

```python
from buraq.signals import pre_save, post_save, pre_delete, post_delete
```

## Connecting a handler

```python
from buraq.signals import post_save
from posts.models import Post


@post_save.connect
async def on_post_saved(sender, instance, created, **kwargs):
    if created:
        print(f"New post: {instance.title}")
    else:
        print(f"Post updated: {instance.title}")
```

## Sender filtering

Only fire for a specific model:

```python
@post_save.connect
async def on_post_saved(sender, instance, created, **kwargs):
    if sender is not Post:
        return
    await notify_subscribers(instance)
```

## Model init signals — pre_init / post_init

`pre_init` and `post_init` fire synchronously around `Model.__init__` so you can inspect or mutate the kwargs before the instance is built.

```python
from buraq.signals import pre_init, post_init
from myapp.models import Post

@pre_init.connect
def on_pre_init(sender, args, kwargs, **extra):
    # kwargs is the dict passed to Post(...)
    if sender is Post:
        kwargs.setdefault("status", "draft")

@post_init.connect
def on_post_init(sender, instance, **extra):
    # instance is fully constructed
    print(f"Post created: {instance.title!r}")
```

!!! note
    Because `Model.__init__` is synchronous, only **non-async** handlers are called for `pre_init` / `post_init`. Async handlers registered for these signals are silently skipped. Use `post_save` for async work that must run after construction and database save.

## send_sync() — synchronous dispatch

`Signal.send_sync()` fires all registered **non-coroutine** handlers synchronously. It is used internally for `pre_init` / `post_init` and is available for your own signals when called from a context without an event loop:

```python
from buraq.signals import Signal

my_signal = Signal()

@my_signal.connect
def sync_handler(sender, value, **kwargs):
    print(f"Got: {value}")

# Call from sync code (no running loop required)
my_signal.send_sync(sender=None, value=42)
```

## Sync handlers

Sync handlers are automatically run in a thread pool so they don't block the event loop:

```python
@post_save.connect
def on_post_saved_sync(sender, instance, created, **kwargs):
    # runs in asyncio.to_thread() automatically
    send_webhook(instance.id)
```

## Sending a signal manually

```python
from buraq.signals import Signal

# Define
order_completed = Signal()

# Send
await order_completed.send(sender=Order, instance=order, total=99.99)

# Receive
@order_completed.connect
async def on_order_completed(sender, instance, total, **kwargs):
    await send_receipt_email(instance.user.email, total)
```

## Disconnecting

```python
post_save.disconnect(on_post_saved)
```

## Weak references

By default, signals hold a **strong** reference to the handler so it is never
garbage-collected while the signal exists.  Pass `weak=True` to hold only a
weak reference — the handler is automatically unregistered when it is collected:

```python
post_save.connect(on_post_saved, weak=True)
```

!!! warning
    `weak=True` only makes sense for module-level functions stored in a
    long-lived variable.  Avoid it for lambdas or locally-defined functions —
    they will be collected immediately and the handler will never fire.

## dispatch_uid — deduplication

Prevent the same handler from being registered twice (common in tests that
import and re-import modules):

```python
post_save.connect(
    on_post_saved,
    dispatch_uid="posts.handlers.on_post_saved",
)
```

If `connect()` is called again with the same `dispatch_uid`, the existing
registration is replaced rather than duplicated.

## connect_via() — sender-scoped shortcut

```python
from buraq.signals import post_save
from posts.models import Post

@post_save.connect_via(Post)
async def on_post_saved(sender, instance, created, **kwargs):
    await notify_subscribers(instance)
```

Equivalent to `signal.connect(handler, sender=Post)` but cleaner as a decorator.

## send_robust() — catch handler exceptions

`send()` lets exceptions propagate. `send_robust()` catches them and returns them as values:

```python
responses = await my_signal.send_robust(sender=MyModel, instance=obj)
for handler, result in responses:
    if isinstance(result, Exception):
        print(f"Handler {handler.__name__} raised: {result}")
```

## Available built-in signals

### Model signals

| Signal | When fired | Extra kwargs |
|---|---|---|
| `pre_save` | Before a model instance is saved | `instance`, `created` |
| `post_save` | After a model instance is saved | `instance`, `created` |
| `pre_delete` | Before a model instance is deleted | `instance` |
| `post_delete` | After a model instance is deleted | `instance` |
| `pre_init` | Before a model `__init__` runs | `args`, `kwargs` |
| `post_init` | After a model `__init__` completes | `instance` |
| `class_prepared` | After a model class body is fully prepared | — |

### Many-to-many signal

`m2m_changed` fires around every `_M2MManager` mutation (`add`, `remove`, `set`, `clear`).

```python
from buraq.signals import m2m_changed
from posts.models import Post

@m2m_changed.connect
async def on_tags_changed(sender, action, instance, model, pk_set, **kwargs):
    if action == "post_add":
        print(f"Tags {pk_set} added to post {instance.id}")
```

| `action` value | When |
|---|---|
| `"pre_add"` | Before new M2M rows are inserted |
| `"post_add"` | After new M2M rows are inserted |
| `"pre_remove"` | Before M2M rows are deleted |
| `"post_remove"` | After M2M rows are deleted |
| `"pre_clear"` | Before all M2M rows for this instance are deleted |
| `"post_clear"` | After all M2M rows are deleted |

Extra kwargs: `sender` (through-table class), `action`, `instance` (source model instance), `reverse=False`, `model` (target model class), `pk_set` (set of affected PKs, or `None` for `clear`).

### Migration signals

| Signal | When fired | Extra kwargs |
|---|---|---|
| `pre_migrate` | Before migration runs begin | `app_config`, `verbosity`, `interactive`, `using` |
| `post_migrate` | After all migrations complete | `app_config`, `verbosity`, `interactive`, `using` |

```python
from buraq.signals import post_migrate

@post_migrate.connect
async def seed_data(sender, **kwargs):
    await Permission.objects.get_or_create(codename="view_dashboard")
```

### Request lifecycle signals

| Signal | When fired | Extra kwargs |
|---|---|---|
| `request_started` | On every incoming HTTP request | `environ` |
| `request_finished` | After every HTTP response is sent | — |
| `got_request_exception` | When an unhandled exception occurs | `request` |

### Settings signal

| Signal | When fired | Extra kwargs |
|---|---|---|
| `setting_changed` | When a setting is modified at runtime (tests) | `setting`, `value`, `enter` |

```python
from buraq.signals import request_started, got_request_exception

@request_started.connect
async def log_request(sender, environ, **kwargs):
    print(f"Request: {environ.get('REQUEST_METHOD')} {environ.get('PATH_INFO')}")

@got_request_exception.connect
async def log_exception(sender, request, **kwargs):
    import traceback
    traceback.print_exc()
```
