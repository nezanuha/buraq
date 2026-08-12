"""
In-memory email backend — stores sent messages in a module-level list.

No email is actually delivered.  Useful in tests::

    # config/settings.py
    EMAIL_BACKEND = "buraq.contrib.email.backends.locmem.EmailBackend"

    # In tests — always call clear_outbox() in tearDown or an autouse fixture:
    from buraq.contrib.email.backends.locmem import outbox, clear_outbox

    await send_mail("Hi", "Hello", ["to@example.com"])
    assert len(outbox) == 1
    assert outbox[0].subject == "Hi"
    clear_outbox()  # reset between tests
"""
from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from buraq.contrib.email.backends.base import BaseEmailBackend

if TYPE_CHECKING:
    from buraq.contrib.email.message import EmailMessage

_log = logging.getLogger("buraq.email")
_OUTBOX_WARN_THRESHOLD = 500

# Global in-memory inbox — accessible as `from buraq.contrib.email.backends.locmem import outbox`
outbox: list[EmailMessage] = []
_lock = threading.Lock()


def clear_outbox() -> None:
    """Empty the in-memory outbox."""
    with _lock:
        outbox.clear()


class EmailBackend(BaseEmailBackend):
    """
    Store all sent messages in the module-level ``outbox`` list.

    Thread-safe: uses a lock when appending.
    Call ``clear_outbox()`` between tests to prevent unbounded memory growth.

    Usage::

        EMAIL_BACKEND = "buraq.contrib.email.backends.locmem.EmailBackend"
    """

    async def send(self, message: EmailMessage) -> bool:
        with _lock:
            outbox.append(message)
            size = len(outbox)
        if size > _OUTBOX_WARN_THRESHOLD:
            _log.warning(
                "locmem outbox has %d messages. Call clear_outbox() between tests "
                "to prevent unbounded memory growth.",
                size,
            )
        return True

    async def send_many(self, messages: list[EmailMessage]) -> int:
        with _lock:
            outbox.extend(messages)
            size = len(outbox)
        if size > _OUTBOX_WARN_THRESHOLD:
            _log.warning(
                "locmem outbox has %d messages. Call clear_outbox() between tests "
                "to prevent unbounded memory growth.",
                size,
            )
        return len(messages)
