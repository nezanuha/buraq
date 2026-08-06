"""
Signals — sync/async event dispatch for decoupled application logic.

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
import weakref
from collections.abc import Callable


class Signal:
    def __init__(self, providing_args: list = None):
        # Each entry: (sender_filter, handler_ref, dispatch_uid | None)
        # handler_ref is a weakref.ref (or weakref.WeakMethod) when weak=True,
        # or the callable itself when weak=False.
        self._receivers: list[tuple] = []
        self.providing_args = providing_args or []

    def _make_ref(self, func, weak: bool):
        if not weak:
            return func
        if inspect.ismethod(func):
            return weakref.WeakMethod(func)
        return weakref.ref(func)

    def _resolve_ref(self, ref):
        """Return the live callable or None if the weakref is dead."""
        if callable(ref) and not isinstance(ref, weakref.ref):
            return ref
        return ref()

    def connect(self, receiver=None, sender=None, weak=True, dispatch_uid=None):
        """
        Connect a receiver function.

        Can be used as a decorator (no args) or called directly:
            @signal.connect
            def handler(sender, **kwargs): ...

            signal.connect(handler, sender=MyModel)
        """
        if receiver is None:
            def decorator(func):
                self._do_connect(func, sender=sender, weak=weak, dispatch_uid=dispatch_uid)
                return func
            return decorator

        if callable(receiver):
            self._do_connect(receiver, sender=sender, weak=weak, dispatch_uid=dispatch_uid)
            return receiver

        return receiver

    def _do_connect(self, func, sender, weak, dispatch_uid):
        if dispatch_uid is not None:
            # Deduplicate — remove existing entry with same uid before adding.
            self._receivers = [
                entry for entry in self._receivers if entry[2] != dispatch_uid
            ]
        ref = self._make_ref(func, weak)
        self._receivers.append((sender, ref, dispatch_uid))

    def connect_via(self, sender, weak=True, dispatch_uid=None):
        """Shortcut decorator: @signal.connect_via(MyModel)"""
        def decorator(func):
            self._do_connect(func, sender=sender, weak=weak, dispatch_uid=dispatch_uid)
            return func
        return decorator

    def disconnect(self, receiver, sender=None):
        def _matches(entry):
            _, ref, _ = entry
            live = self._resolve_ref(ref)
            return live is receiver and (sender is None or entry[0] is sender)
        self._receivers = [e for e in self._receivers if not _matches(e)]

    def _live_receivers(self, sender):
        """Yield (handler, ) for all live receivers matching sender, pruning dead weakrefs."""
        alive = []
        for entry in self._receivers:
            sender_filter, ref, uid = entry
            live = self._resolve_ref(ref)
            if live is None:
                continue  # weakref is dead — skip and don't re-add
            alive.append(entry)
            if sender_filter is None or sender_filter is sender:
                yield live
        self._receivers = alive

    async def send(self, sender, **kwargs) -> list:
        """Call all matching receivers. Supports both sync and async handlers.
        Sync handlers are run in a thread pool to avoid blocking the event loop."""
        responses = []
        for handler in self._live_receivers(sender):
            if inspect.iscoroutinefunction(handler):
                result = await handler(sender=sender, **kwargs)
            else:
                result = await asyncio.to_thread(handler, sender=sender, **kwargs)
            responses.append((handler, result))
        return responses

    async def send_robust(self, sender, **kwargs) -> list:
        """Like send() but catches exceptions instead of raising."""
        responses = []
        for handler in self._live_receivers(sender):
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
