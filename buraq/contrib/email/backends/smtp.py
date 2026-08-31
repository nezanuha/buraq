import contextlib
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

    async def send_many(self, messages: list["EmailMessage"]) -> int:
        """Send every message over one connection.

        The inherited implementation loops over ``send()``, and ``send()`` uses
        aiosmtplib's one-shot helper -- which opens a connection, negotiates
        TLS, authenticates and quits, per message. A hundred messages meant a
        hundred handshakes, each of them slower than the send itself, which is
        the entire cost this method exists to avoid.

        A failure on one message does not abandon the rest: the count returned
        is how many were accepted, the same as the base class.
        """
        if not messages:
            return 0
        if len(messages) == 1:
            return 1 if await self.send(messages[0]) else 0

        client = aiosmtplib.SMTP(
            hostname=self.host, port=self.port, start_tls=self.use_tls
        )
        try:
            await client.connect()
        except Exception:
            _log.exception("SMTP connect failed for %s:%s", self.host, self.port)
            return 0

        sent = 0
        try:
            if self.username:
                await client.login(self.username, self.password)
            for message in messages:
                recipients = message.to + message.cc + message.bcc
                try:
                    await client.send_message(message.build_mime(), recipients=recipients)
                    sent += 1
                except Exception:
                    _log.exception("SMTP error sending to %s", recipients)
        except Exception:
            _log.exception("SMTP login failed for %s:%s", self.host, self.port)
        finally:
            # The messages are already accepted; a failure closing the
            # connection would report a send that happened as one that did not.
            with contextlib.suppress(Exception):
                await client.quit()
        return sent
