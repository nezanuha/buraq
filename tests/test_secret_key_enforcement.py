"""
Where an insecure SECRET_KEY is caught.

It used to be enforced while `buraq.conf.defaults` was being imported, so any
`import buraq` raised on a machine with no project configured — including
`buraq startproject`, the first command anyone runs. The system checks already
covered the same ground and run at application startup, which is the point where
serving with a placeholder key actually matters.
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest

from buraq.conf.defaults import INSECURE_SECRET_KEY

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_importing_buraq_without_a_secret_key_works(tmp_path):
    """Scaffolding a project cannot require the project that does not exist yet."""
    env = {
        k: v for k, v in os.environ.items() if k not in ("SECRET_KEY", "DEBUG")
    }
    env["PYTHONPATH"] = str(REPO_ROOT)

    result = subprocess.run(
        [sys.executable, "-c", "import buraq; print('IMPORTED')"],
        cwd=tmp_path,          # no .env, no settings module
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert "IMPORTED" in result.stdout, result.stderr


def test_the_placeholder_key_is_one_constant():
    """The field default and the check compared two copies of the same literal."""
    from buraq.conf.defaults import BuraqSettings

    assert BuraqSettings.model_fields["SECRET_KEY"].default == INSECURE_SECRET_KEY


def test_the_check_flags_the_placeholder_key():
    from buraq.checks.security import check_secret_key

    class _Settings:
        SECRET_KEY = INSECURE_SECRET_KEY

    messages = check_secret_key(_Settings())

    assert [m.id for m in messages] == ["security.E001"]


def test_a_real_key_passes():
    from buraq.checks.security import check_secret_key

    class _Settings:
        SECRET_KEY = "x" * 60

    assert check_secret_key(_Settings()) == []


def test_serving_with_the_placeholder_key_is_refused(monkeypatch):
    """The guarantee worth keeping: production must not start on a placeholder."""
    from buraq.conf import settings
    from buraq.core.application import Buraq
    from buraq.exceptions import ImproperlyConfigured

    monkeypatch.setattr(settings, "SECRET_KEY", INSECURE_SECRET_KEY)
    monkeypatch.setattr(settings, "DEBUG", False)
    app = Buraq()

    with pytest.raises(ImproperlyConfigured, match="security.E001"):
        asyncio.run(app._on_startup())


def test_debug_reports_but_does_not_block(monkeypatch, capsys):
    """Local development should be told, not stopped."""
    from buraq.conf import settings
    from buraq.core.application import Buraq

    monkeypatch.setattr(settings, "SECRET_KEY", INSECURE_SECRET_KEY)
    monkeypatch.setattr(settings, "DEBUG", True)
    app = Buraq()

    asyncio.run(app._on_startup())

    assert "security.E001" in capsys.readouterr().err
