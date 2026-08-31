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


# ── open(): a connection to work between sends on ────────────────────────────

async def test_open_keeps_one_connection_across_a_loop(client, monkeypatch):
    """The case send_many cannot cover: logic between the sends.

    Django does this with `with mail.get_connection() as connection:`. Without
    it the only way to filter while sending was a loop of send(), which is a
    connection per message.
    """
    backend = _backend(monkeypatch)
    rows = [("a@x.c", True), ("b@x.c", False), ("c@x.c", True)]

    async with backend.open() as connection:
        for address, wants_email in rows:
            if wants_email:
                await connection.send(
                    EmailMessage(subject="hi", body="b", to=[address], from_email="s@x.c")
                )

    assert len(_FakeClient.instances) == 1
    assert _FakeClient.instances[0].sent == [["a@x.c"], ["c@x.c"]]


async def test_open_closes_on_the_way_out(client, monkeypatch):
    async with _backend(monkeypatch).open():
        pass
    assert _FakeClient.instances[0].quit_called


async def test_open_closes_even_when_the_block_raises(client, monkeypatch):
    with pytest.raises(RuntimeError):
        async with _backend(monkeypatch).open() as connection:
            await connection.send(_messages(1)[0])
            raise RuntimeError("boom")

    assert _FakeClient.instances[0].quit_called, "a leaked connection outlives the process"


async def test_open_logs_in_once(client, monkeypatch):
    backend = _backend(monkeypatch, username="user", password="pw")
    async with backend.open() as connection:
        for message in _messages(3):
            await connection.send(message)

    assert _FakeClient.instances[0].logged_in is True
    assert len(_FakeClient.instances) == 1


async def test_a_connection_that_will_not_open_reports_failure(client, monkeypatch):
    """Rather than raising: send() already returns False on a bad send."""

    async def refuse(self):
        raise OSError("connection refused")

    monkeypatch.setattr(_FakeClient, "connect", refuse)
    async with _backend(monkeypatch).open() as connection:
        assert await connection.send(_messages(1)[0]) is False


async def test_two_blocks_do_not_share_a_connection(client, monkeypatch):
    """get_connection() caches backends, so state on one would be shared.

    Two blocks over the same backend must each get their own client, or the
    first to finish closes the connection the second is still using.
    """
    backend = _backend(monkeypatch)

    async with backend.open() as first, backend.open() as second:
        await first.send(_messages(1)[0])
        await second.send(_messages(1)[0])

    assert len(_FakeClient.instances) == 2
    assert _FakeClient.instances[0] is not _FakeClient.instances[1]


async def test_a_backend_with_nothing_to_open_still_works(client, monkeypatch):
    """Console, file and in-memory backends have no connection to hold."""
    from buraq.contrib.email.backends.locmem import EmailBackend

    backend = EmailBackend()
    async with backend.open() as connection:
        assert connection is backend
