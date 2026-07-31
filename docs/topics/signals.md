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

## Available built-in signals

| Signal | When fired | Extra kwargs |
|---|---|---|
| `pre_save` | Before a model instance is saved | `instance`, `created` |
| `post_save` | After a model instance is saved | `instance`, `created` |
| `pre_delete` | Before a model instance is deleted | `instance` |
| `post_delete` | After a model instance is deleted | `instance` |
