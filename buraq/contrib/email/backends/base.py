from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from buraq.contrib.email.message import EmailMessage


class BaseEmailBackend(ABC):
    @abstractmethod
    async def send(self, message: "EmailMessage") -> bool: ...

    async def send_many(self, messages: list["EmailMessage"]) -> int:
        sent = 0
        for msg in messages:
            if await self.send(msg):
                sent += 1
        return sent

    def open(self):
        """A connection to send several messages over, as a context manager::

            async with backend.open() as connection:
                for row in rows:
                    if row.wants_email:
                        await connection.send(build(row))

        Most backends have nothing to open -- writing to a console, a file or a
        list costs nothing to repeat -- so this hands back the backend itself
        and the block changes nothing.

        A backend that does hold a connection returns a *new* object owning it
        rather than storing it on itself: get_connection() caches backends and
        hands the same instance to every caller, so state kept on one would be
        shared between concurrent blocks.
        """
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None
