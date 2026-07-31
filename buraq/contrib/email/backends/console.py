from typing import TYPE_CHECKING

from buraq.contrib.email.backends.base import BaseEmailBackend

if TYPE_CHECKING:
    from buraq.contrib.email.message import EmailMessage


class ConsoleEmailBackend(BaseEmailBackend):
    """Prints emails to stdout — use in development."""

    async def send(self, message: "EmailMessage") -> bool:
        separator = "=" * 60
        print(f"\n{separator}")
        print(f"[Email] To: {', '.join(message.to)}")
        print(f"[Email] Subject: {message.subject}")
        print(f"[Email] Body:\n{message.body}")
        if message.attachments:
            print(f"[Email] Attachments: {[a[0] for a in message.attachments]}")
        print(f"{separator}\n")
        return True
