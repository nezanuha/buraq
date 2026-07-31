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
