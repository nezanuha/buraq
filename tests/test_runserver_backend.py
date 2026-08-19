"""
Choosing an ASGI server.

Granian is a required dependency, so it is normally present. It is a compiled
Rust extension though, and one that imports cleanly can still fail to serve on
a given machine -- so `runserver` must never leave the developer with no server
at all just because granian is unavailable or broken.
"""

import sys

import pytest
import typer
import uvicorn

from buraq.management.cli import runserver


@pytest.fixture
def served(monkeypatch):
    """Capture what uvicorn would have been asked to run, without running it."""
    calls = {}

    def fake_run(app, **kwargs):
        calls["app"] = app
        calls.update(kwargs)

    monkeypatch.setattr(uvicorn, "run", fake_run)
    return calls


def _runserver(**overrides):
    kwargs = dict(
        bind="main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        workers=1,
        server="auto",
    )
    kwargs.update(overrides)
    runserver(**kwargs)


def test_uvicorn_runs_when_asked_for(served):
    _runserver(server="uvicorn")

    assert served["app"] == "main:app"
    assert served["port"] == 8000


def test_a_missing_granian_falls_back_to_uvicorn(monkeypatch, served):
    """Auto mode must degrade to a working server, not fail."""
    monkeypatch.setitem(sys.modules, "granian", None)  # makes `import granian` raise

    _runserver(server="auto")

    assert served["app"] == "main:app"


def test_asking_for_granian_explicitly_reports_it_is_missing(monkeypatch, served):
    """Silently serving something else would misrepresent what is running."""
    monkeypatch.setitem(sys.modules, "granian", None)

    with pytest.raises(typer.Exit):
        _runserver(server="granian")

    assert served == {}


def test_the_reloader_gets_the_working_directory(monkeypatch, served):
    """
    Uvicorn's reloader runs the app in a subprocess that does not inherit
    sys.path, so the project directory has to be passed explicitly or the
    reloaded process cannot import the app.
    """
    monkeypatch.setitem(sys.modules, "granian", None)

    _runserver(server="uvicorn", reload=True)

    assert "app_dir" in served
