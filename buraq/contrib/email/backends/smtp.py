import logging
from typing import TYPE_CHECKING

import aiosmtplib

from buraq.conf import settings
from buraq.contrib.email.backends.base import BaseEmailBackend

if TYPE_CHECKING:
    from buraq.contrib.email.message import EmailMessage

_log = logging.getLogger(__name__)


class SMTPEmailBackend(BaseEmailBackend):
    """Async SMTP email backend — production ready."""

    def __init__(self, **kwargs):
        self.host = kwargs.get("HOST") or settings.EMAIL_HOST or "localhost"
        self.port = int(kwargs.get("PORT", settings.EMAIL_PORT))
        self.username = kwargs.get("HOST_USER") or settings.EMAIL_HOST_USER
        self.password = kwargs.get("HOST_PASSWORD") or settings.EMAIL_HOST_PASSWORD
        self.use_tls = kwargs.get("USE_TLS", settings.EMAIL_USE_TLS)

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
        except Exception:
            _log.exception(
                "SMTP error sending to %s via %s:%s",
                all_recipients, self.host, self.port,
            )
            return False
