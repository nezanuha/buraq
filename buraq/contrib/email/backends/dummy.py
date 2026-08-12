"""
Dummy email backend — silently discards all messages.

Useful in production-like environments where you want to suppress email sending
without printing to the console::

    EMAIL_BACKEND = "buraq.contrib.email.backends.dummy.DummyEmailBackend"
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from buraq.contrib.email.backends.base import BaseEmailBackend

if TYPE_CHECKING:
    from buraq.contrib.email.message import EmailMessage


class DummyEmailBackend(BaseEmailBackend):
    """Accepts messages but does nothing with them."""

    async def send(self, message: "EmailMessage") -> bool:
        return True

    async def send_many(self, messages: list["EmailMessage"]) -> int:
        return len(messages)
