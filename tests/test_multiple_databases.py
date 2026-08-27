"""
Reads can be sent to a replica; writes never are.

The correctness question is not which database a query reaches but when routing
must be overridden: a replica is behind the primary by however long replication
takes, so a transaction that writes a row and then reads it back has to be
answered by the primary or it sees stale data.
"""

import asyncio

import pytest

from buraq.conf import settings
from buraq.core.db import (
    DEFAULT_DB_ALIAS,
    _current_session,
    connection,
    database_urls,
    read_alias,
    reset_connections,
    routing_alias,
)
from buraq.exceptions import ImproperlyConfigured


@pytest.fixture
def two_databases(monkeypatch, tmp_path):
    primary = str(tmp_path / "primary.db").replace("\\", "/")
    replica = str(tmp_path / "replica.db").replace("\\", "/")
    monkeypatch.setattr(settings, "DATABASES", {
        "default": f"sqlite+aiosqlite:///{primary}",
        "replica": f"sqlite+aiosqlite:///{replica}",
    }, raising=False)
    monkeypatch.setattr(settings, "DATABASE_READ_REPLICAS", ["replica"], raising=False)
    reset_connections()
    yield
    reset_connections()


# ── Configuration ────────────────────────────────────────────────────────────

def test_database_url_is_still_the_single_database_form(monkeypatch):
    """A project that sets neither DATABASES nor a replica is unaffected."""
    monkeypatch.setattr(settings, "DATABASES", {}, raising=False)
    monkeypatch.setattr(settings, "DATABASE_READ_REPLICAS", [], raising=False)
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///./x.db", raising=False)
    reset_connections()
    assert database_urls() == {DEFAULT_DB_ALIAS: "sqlite+aiosqlite:///./x.db"}
    assert read_alias() == DEFAULT_DB_ALIAS


def test_a_replica_that_does_not_exist_is_reported(monkeypatch):
    """Naming one DATABASES does not define used to fail as a query, not config."""
    monkeypatch.setattr(settings, "DATABASES", {
        "default": "sqlite+aiosqlite:///d.db",
    }, raising=False)
    monkeypatch.setattr(settings, "DATABASE_READ_REPLICAS", ["nope"], raising=False)
    reset_connections()
    with pytest.raises(ImproperlyConfigured, match="nope"):
        read_alias()


def test_databases_must_have_a_default(monkeypatch):
    monkeypatch.setattr(settings, "DATABASES", {"replica": "sqlite+aiosqlite:///r.db"},
                        raising=False)
    with pytest.raises(ImproperlyConfigured) as exc:
        database_urls()
    assert "default" in str(exc.value)


def test_an_unknown_alias_says_what_is_configured(two_databases):
    with pytest.raises(ImproperlyConfigured) as exc:
        connection("nope")
    message = str(exc.value)
    assert "nope" in message and "default" in message and "replica" in message


# ── Routing ──────────────────────────────────────────────────────────────────

def test_reads_go_to_a_replica_and_writes_do_not(two_databases):
    assert routing_alias(write=False) == "replica"
    assert routing_alias(write=True) == DEFAULT_DB_ALIAS


def test_using_overrides_routing_in_both_directions(two_databases):
    assert routing_alias(write=False, using="default") == "default"
    assert routing_alias(write=True, using="replica") == "replica"


def test_a_read_inside_a_transaction_goes_to_the_primary(two_databases):
    """Otherwise a transaction cannot read back what it just wrote."""
    token = _current_session.set(object())      # stand in for an open atomic block
    try:
        assert routing_alias(write=False) == DEFAULT_DB_ALIAS
    finally:
        _current_session.reset(token)


def test_replicas_are_used_in_rotation(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DATABASES", {
        "default": "sqlite+aiosqlite:///d.db",
        "r1": "sqlite+aiosqlite:///1.db",
        "r2": "sqlite+aiosqlite:///2.db",
    }, raising=False)
    monkeypatch.setattr(settings, "DATABASE_READ_REPLICAS", ["r1", "r2"], raising=False)
    reset_connections()          # the replica list is resolved once and cached
    picked = {read_alias() for _ in range(10)}
    assert picked == {"r1", "r2"}


def test_default_is_never_treated_as_a_replica(monkeypatch):
    """Listing it would make the rotation send reads to the primary at random."""
    monkeypatch.setattr(settings, "DATABASES", {"default": "sqlite+aiosqlite:///d.db"},
                        raising=False)
    monkeypatch.setattr(settings, "DATABASE_READ_REPLICAS", ["default"], raising=False)
    reset_connections()
    assert read_alias() == DEFAULT_DB_ALIAS


# ── The queryset ─────────────────────────────────────────────────────────────

def test_using_survives_further_chaining():
    """using() early in a chain must not be dropped by the calls after it."""
    from buraq.orm import fields
    from buraq.orm.base import Model

    class Chained(Model):
        __app_label__ = "multidb_chain"
        title = fields.CharField(max_length=100)

    qs = Chained.objects.using("replica").filter(title="x").order_by("-id").distinct()
    assert qs._using == "replica"

    # And the other order, since using() is just another chaining method.
    qs = Chained.objects.filter(title="x").using("replica").order_by("-id")
    assert qs._using == "replica"

    # A queryset nobody routed carries nothing, so the router decides.
    assert Chained.objects.filter(title="x")._using is None


def test_reads_and_writes_reach_the_database_they_were_routed_to(two_databases):
    """End to end: two real files, each holding a row the other does not."""
    from buraq.core.db import Base
    from buraq.orm import fields
    from buraq.orm.base import Model

    class Note(Model):
        __app_label__ = "multidb_test"
        title = fields.CharField(max_length=100)

    async def scenario():
        for alias, title in (("default", "primary row"), ("replica", "replica row")):
            async with connection(alias).begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with connection(alias)() as session:
                session.add(Note(title=title))
                await session.commit()

        plain = await Note.objects.all()
        forced_primary = await Note.objects.using("default").all()
        forced_replica = await Note.objects.using("replica").all()
        return plain[0].title, forced_primary[0].title, forced_replica[0].title

    plain, primary, replica = asyncio.run(scenario())
    assert plain == "replica row", "an unrouted read should have gone to the replica"
    assert primary == "primary row"
    assert replica == "replica row"
