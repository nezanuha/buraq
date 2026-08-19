"""
Sending signals from the sync CLI, and finding the settings module.

``Signal.send`` is a coroutine. The CLI called it without awaiting, so
``pre_migrate``/``post_migrate`` produced a RuntimeWarning and no receiver ever
ran -- and the surrounding ``except Exception: pass`` meant nothing said so.
"""

import logging

import pytest

from buraq.apps import apps
from buraq.management.cli import _discover_settings_module, _fire_signal
from buraq.signals import Signal


@pytest.fixture(autouse=True)
def fresh_registry():
    """_fire_signal loads app configs; keep that out of other tests."""
    saved = (dict(apps._apps), apps._ready, apps._hooks_ran)
    yield
    apps._apps, apps._ready, apps._hooks_ran = dict(saved[0]), saved[1], saved[2]


@pytest.fixture
def a_signal(monkeypatch):
    """A throwaway signal reachable by name, the way _fire_signal looks one up."""
    import buraq.signals

    sig = Signal()
    monkeypatch.setattr(buraq.signals, "test_only_signal", sig, raising=False)
    return sig


def test_an_async_receiver_actually_runs(a_signal):
    """The regression: the coroutine was created and dropped."""
    seen = []

    async def receiver(sender, **kwargs):
        seen.append(kwargs.get("revision"))

    a_signal.connect(receiver)
    _fire_signal("test_only_signal", revision="head")

    assert seen == ["head"]


def test_a_sync_receiver_also_runs(a_signal):
    seen = []

    def receiver(sender, **kwargs):
        seen.append(kwargs.get("revision"))

    a_signal.connect(receiver)
    _fire_signal("test_only_signal", revision="head")

    assert seen == ["head"]


def test_a_failing_receiver_is_reported_but_does_not_fail_the_command(a_signal, caplog):
    """The migration already ran; a bad receiver must not make it look otherwise."""

    async def receiver(sender, **kwargs):
        raise RuntimeError("receiver exploded")

    a_signal.connect(receiver)

    with caplog.at_level(logging.ERROR, logger="buraq.signals"):
        _fire_signal("test_only_signal", revision="head")  # must not raise

    assert "receiver exploded" in caplog.text


def test_an_unknown_signal_name_is_a_no_op():
    _fire_signal("no_such_signal", revision="head")


# ─── Locating the settings module ─────────────────────────────────────────────

def test_conventional_config_package_is_found(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "settings.py").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert _discover_settings_module() == "config.settings"


def test_top_level_settings_module_is_found(tmp_path, monkeypatch):
    (tmp_path / "settings.py").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert _discover_settings_module() == "settings"


def test_a_single_package_holding_settings_is_found(tmp_path, monkeypatch):
    pkg = tmp_path / "myproject"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "settings.py").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert _discover_settings_module() == "myproject.settings"


def test_two_candidates_are_not_guessed_between(tmp_path, monkeypatch):
    for name in ("one", "two"):
        pkg = tmp_path / name
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "settings.py").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert _discover_settings_module() is None


def test_no_settings_anywhere_yields_nothing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert _discover_settings_module() is None
