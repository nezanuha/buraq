"""
A new project should have somewhere for tests, and something in it.

pyproject.toml already pointed pytest at `tests`, and the directory did not
exist -- so the first `buraq test` on a fresh project collected nothing and
exited 0, which reads like a broken runner rather than like there is nowhere to
look.
"""

import subprocess
import sys


def _project(tmp_path):
    subprocess.run(
        [sys.executable, "-m", "buraq", "startproject", "site"],
        cwd=tmp_path, capture_output=True, text=True, check=True,
    )
    return tmp_path / "site"


def test_the_tests_directory_exists(tmp_path):
    assert (_project(tmp_path) / "tests").is_dir()


def test_pytest_is_pointed_at_it(tmp_path):
    config = _project(tmp_path).joinpath("pyproject.toml").read_text(encoding="utf-8")
    assert 'testpaths = ["tests"]' in config


def test_there_is_something_to_run(tmp_path):
    """Otherwise the first run reports nothing and teaches nothing."""
    smoke = _project(tmp_path) / "tests" / "test_smoke.py"
    assert smoke.exists()

    body = smoke.read_text(encoding="utf-8")
    assert "def test_" in body
    assert "TestClient" in body, "the example should show how to drive the app"
    assert "Delete this" in body, "and say it is meant to be replaced"
