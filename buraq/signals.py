"""
Django-style signals for Buraq.

Usage:
    from buraq.signals import pre_save, post_save, Signal

    # Connect with decorator
    @post_save.connect
    def on_user_save(sender, instance, created, **kwargs):
        if created:
            print(f"New user: {instance.username}")

    # Connect with sender filter
    @post_save.connect_via(User)
    def on_user_save(sender, instance, created, **kwargs): ...

    # Disconnect
    post_save.disconnect(on_user_save, sender=User)

    # Send manually
    my_signal = Signal()
    await my_signal.send(sender=MyClass, instance=obj)
"""
import asyncio
import inspect
from collections.abc import Callable


class Signal:
    def __init__(self, providing_args: list = None):
        self._receivers: list[tuple[type | None, Callable]] = []
        self.providing_args = providing_args or []

    def connect(self, receiver=None, sender=None, weak=True, dispatch_uid=None):
        """
        Connect a receiver function.

        Can be used as a decorator (no args) or called directly:
            @signal.connect
            def handler(sender, **kwargs): ...

            signal.connect(handler, sender=MyModel)
        """
        if receiver is None:
            # Called as @signal.connect(sender=X) — return decorator
            def decorator(func):
                self._receivers.append((sender, func))
                return func
            return decorator

        if callable(receiver):
            # Used as @signal.connect (no parens) or signal.connect(func)
            self._receivers.append((sender, receiver))
            return receiver

        return receiver

    def connect_via(self, sender):
        """Shortcut decorator: @signal.connect_via(MyModel)"""
        def decorator(func):
            self._receivers.append((sender, func))
            return func
        return decorator

    def disconnect(self, receiver, sender=None):
        self._receivers = [
            (s, r) for s, r in self._receivers
            if not (r is receiver and (sender is None or s is sender))
        ]

    async def send(self, sender, **kwargs) -> list:
        """Call all matching receivers. Supports both sync and async handlers.
        Sync handlers are run in a thread pool to avoid blocking the event loop."""
        responses = []
        for sender_filter, handler in self._receivers:
            if sender_filter is None or sender_filter is sender:
                if inspect.iscoroutinefunction(handler):
                    result = await handler(sender=sender, **kwargs)
                else:
                    result = await asyncio.to_thread(handler, sender=sender, **kwargs)
                responses.append((handler, result))
        return responses

    async def send_robust(self, sender, **kwargs) -> list:
        """Like send() but catches exceptions instead of raising."""
        responses = []
        for sender_filter, handler in self._receivers:
            if sender_filter is None or sender_filter is sender:
                try:
                    if inspect.iscoroutinefunction(handler):
                        result = await handler(sender=sender, **kwargs)
                    else:
                        result = await asyncio.to_thread(handler, sender=sender, **kwargs)
                    responses.append((handler, result))
                except Exception as e:
                    responses.append((handler, e))
        return responses


# ── Built-in model signals ──────────────────────────────────────────────────

pre_save    = Signal(providing_args=["instance", "created"])
post_save   = Signal(providing_args=["instance", "created"])
pre_delete  = Signal(providing_args=["instance"])
post_delete = Signal(providing_args=["instance"])
pre_init    = Signal(providing_args=["args", "kwargs"])
post_init   = Signal(providing_args=["instance"])

# ── Request lifecycle signals ───────────────────────────────────────────────

request_started  = Signal(providing_args=["environ"])
request_finished = Signal()
got_request_exception = Signal(providing_args=["request"])

# ── Management signals ──────────────────────────────────────────────────────

setting_changed = Signal(providing_args=["setting", "value", "enter"])
