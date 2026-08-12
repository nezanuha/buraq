"""
In-memory email backend — alias for ``buraq.contrib.email.backends.locmem``.

Prefer ``locmem`` directly; this module exists for backwards compatibility.

Use in tests::

    EMAIL_BACKEND = "buraq.contrib.email.backends.locmem.EmailBackend"

    from buraq.contrib.email.backends.locmem import outbox, clear_outbox
"""
from buraq.contrib.email.backends.locmem import EmailBackend as InMemoryEmailBackend
from buraq.contrib.email.backends.locmem import outbox

__all__ = ["InMemoryEmailBackend", "outbox"]
