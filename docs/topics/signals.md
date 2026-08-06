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
