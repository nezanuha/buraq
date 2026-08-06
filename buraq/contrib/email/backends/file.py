from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from buraq.conf import settings
from buraq.contrib.email.backends.base import BaseEmailBackend

if TYPE_CHECKING:
    from buraq.contrib.email.message import EmailMessage


class FileEmailBackend(BaseEmailBackend):
    """Saves emails as .eml files — useful for testing/staging."""

    def __init__(self):
        email_dir = getattr(settings, "EMAIL_FILE_PATH", "sent_emails")  # type: ignore[attr-defined]
        self.output_dir = Path(email_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def send(self, message: "EmailMessage") -> bool:
        import asyncio
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        first_recipient = message.to[0].replace("@", "_") if message.to else "no_recipient"
        filename = self.output_dir / f"{timestamp}_{first_recipient}.eml"
        content = message.build_mime().as_string()
        await asyncio.to_thread(filename.write_text, content, "utf-8")
        return True
