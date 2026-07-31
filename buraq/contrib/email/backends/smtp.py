from typing import TYPE_CHECKING

import aiosmtplib

from buraq.conf import settings
from buraq.contrib.email.backends.base import BaseEmailBackend

if TYPE_CHECKING:
    from buraq.contrib.email.message import EmailMessage


class SMTPEmailBackend(BaseEmailBackend):
    """Async SMTP email backend — production ready."""

    def __init__(self):
        self.host = settings.EMAIL_HOST or "localhost"
        self.port = settings.EMAIL_PORT
        self.username = settings.EMAIL_HOST_USER
        self.password = settings.EMAIL_HOST_PASSWORD
        self.use_tls = settings.EMAIL_USE_TLS

    async def send(self, message: "EmailMessage") -> bool:
        mime = message.build_mime()
        all_recipients = message.to + message.cc + message.bcc

        try:
            await aiosmtplib.send(
                mime,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                start_tls=self.use_tls,
                recipients=all_recipients,
            )
            return True
        except Exception as e:
            if settings.DEBUG:
                print(f"[Email] SMTP error: {e}")
            return False
