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

        async with self.open() as connection:
            return await connection.send_many(messages)

    def open(self) -> "_OpenSMTPConnection":
        """A live connection to send several messages over.

        Used as ``async with backend.open() as connection:``. A new object each
        time rather than state on ``self``: get_connection() caches backends, so
        two blocks running at once would otherwise share -- and close -- one
        client. It is also why this is a method and not ``__aenter__`` on the
        backend: Python calls ``__aexit__`` on the object the ``with`` names, so
        a backend handing out a different object would never see it closed.
        """
        client = aiosmtplib.SMTP(
            hostname=self.host, port=self.port, start_tls=self.use_tls
        )
        return _OpenSMTPConnection(client, self)


class _OpenSMTPConnection(BaseEmailBackend):
    """A live SMTP connection, sending without reconnecting.

    Handed out by ``SMTPEmailBackend.open()`` so that a loop can do work between
    sends -- read a row, check a flag, wait -- and still pay for the handshake
    once. ``send_many()`` covers the case where the messages are all known up
    front and needs no block.
    """

    def __init__(self, client, backend: "SMTPEmailBackend"):
        self._client = client
        self._backend = backend
        #: False until the connection opens, and again once it closes. Sends
        #: then report failure rather than raising, which is how send() behaves.
        self.usable = False

    async def send(self, message: "EmailMessage") -> bool:
        if not self.usable:
            return False
        recipients = message.to + message.cc + message.bcc
        try:
            await self._client.send_message(message.build_mime(), recipients=recipients)
            return True
        except Exception:
            _log.exception("SMTP error sending to %s", recipients)
            return False

    async def aclose(self) -> None:
        if self.usable:
            # Messages already accepted are sent; a failure closing would report
            # one that happened as one that did not.
            with contextlib.suppress(Exception):
                await self._client.quit()
        self.usable = False

    async def __aenter__(self) -> "_OpenSMTPConnection":
        backend = self._backend
        try:
            await self._client.connect()
            if backend.username:
                await self._client.login(backend.username, backend.password)
            self.usable = True
        except Exception:
            # A server that is down should not take the caller down with it:
            # send() already reports failure rather than raising, and a block
            # that cannot connect reports it for every message in the block.
            _log.exception("SMTP connect failed for %s:%s", backend.host, backend.port)
            self.usable = False
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()
