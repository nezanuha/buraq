"""
send_many() should open one SMTP connection, not one per message.

The inherited implementation loops over send(), and send() uses aiosmtplib's
one-shot helper -- which connects, negotiates TLS, authenticates and quits for
every message. A hundred messages meant a hundred handshakes, each slower than
the send itself, which is the entire cost the method exists to avoid.

Counted against a local server before this was fixed: five messages, five
connections.
"""

import pytest

from buraq.contrib.email.backends import smtp as smtp_backend
from buraq.contrib.email.message import EmailMessage


class _FakeClient:
    """Stands in for aiosmtplib.SMTP, recording what it was asked to do."""

    instances: list["_FakeClient"] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.sent: list[list[str]] = []
        self.logged_in = False
        self.quit_called = False
        _FakeClient.instances.append(self)

    async def connect(self):
        return None

    async def login(self, username, password):
        self.logged_in = True

    async def send_message(self, mime, recipients=None):
        self.sent.append(list(recipients or []))

    async def quit(self):
        self.quit_called = True


@pytest.fixture
def client(monkeypatch):
    _FakeClient.instances = []
    monkeypatch.setattr(smtp_backend.aiosmtplib, "SMTP", _FakeClient)

    one_shot = []

    async def fake_send(mime, **kwargs):
        one_shot.append(kwargs.get("recipients"))

    monkeypatch.setattr(smtp_backend.aiosmtplib, "send", fake_send)
    return one_shot


def _backend(monkeypatch, **over):
    backend = smtp_backend.SMTPEmailBackend.__new__(smtp_backend.SMTPEmailBackend)
    backend.host = over.get("host", "localhost")
    backend.port = over.get("port", 25)
    backend.username = over.get("username", "")
    backend.password = over.get("password", "")
    backend.use_tls = over.get("use_tls", False)
    return backend


def _messages(count):
    return [
        EmailMessage(subject=f"m{i}", body="hi", to=[f"a{i}@b.c"], from_email="x@y.z")
        for i in range(count)
    ]


async def test_many_messages_share_one_connection(client, monkeypatch):
    sent = await _backend(monkeypatch).send_many(_messages(5))

    assert sent == 5
    assert len(_FakeClient.instances) == 1, "one connection for the batch"
    assert len(_FakeClient.instances[0].sent) == 5


async def test_the_connection_is_closed(client, monkeypatch):
    await _backend(monkeypatch).send_many(_messages(3))
    assert _FakeClient.instances[0].quit_called


async def test_login_happens_once_when_credentials_are_set(client, monkeypatch):
    backend = _backend(monkeypatch, username="user", password="pw")
    await backend.send_many(_messages(4))

    assert _FakeClient.instances[0].logged_in is True
    assert len(_FakeClient.instances) == 1


async def test_no_login_without_a_username(client, monkeypatch):
    await _backend(monkeypatch).send_many(_messages(2))
    assert _FakeClient.instances[0].logged_in is False


async def test_one_message_takes_the_simple_path(client, monkeypatch):
    """A batch of one has nothing to amortise, so it uses the one-shot send."""
    sent = await _backend(monkeypatch).send_many(_messages(1))

    assert sent == 1
    assert _FakeClient.instances == [], "no persistent connection for a single message"
    assert len(client) == 1


async def test_nothing_to_send_opens_nothing(client, monkeypatch):
    assert await _backend(monkeypatch).send_many([]) == 0
    assert _FakeClient.instances == []


async def test_one_bad_message_does_not_abandon_the_rest(client, monkeypatch):
    async def fail_on_second(self, mime, recipients=None):
        self.sent.append(list(recipients or []))
        if len(self.sent) == 2:
            raise RuntimeError("rejected")

    monkeypatch.setattr(_FakeClient, "send_message", fail_on_second)
    sent = await _backend(monkeypatch).send_many(_messages(4))

    assert sent == 3, "the failure should cost one message, not the batch"
    assert _FakeClient.instances[0].quit_called


async def test_a_failed_connection_reports_nothing_sent(client, monkeypatch):
    async def refuse(self):
        raise OSError("connection refused")

    monkeypatch.setattr(_FakeClient, "connect", refuse)
    assert await _backend(monkeypatch).send_many(_messages(3)) == 0
