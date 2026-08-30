"""
Where `startproject` puts the project.

The target directory used to be `--dest` only, so the form everyone reaches for
first — `startproject name directory`, the way cp, mv and git clone take theirs
— failed with "Got unexpected extra argument". It is now the second positional,
with --dest kept so anything already scripted keeps working.
"""

import inspect

import pytest
import typer

from buraq.management.cli import startproject


def _params():
    return inspect.signature(startproject).parameters


def test_the_directory_is_a_positional_argument():
    default = _params()["directory"].default

    assert isinstance(default, type(typer.Argument(None)))
    assert default.default is None, "the directory must stay optional"


def test_dest_is_still_accepted():
    """Existing scripts and the previous documentation both use --dest."""
    assert "dest" in _params()


def test_giving_both_the_same_way_twice_is_refused(tmp_path, monkeypatch):
    """
    Silently preferring one would scaffold somewhere the caller did not name.
    """
    monkeypatch.chdir(tmp_path)

    with pytest.raises(typer.Exit) as excinfo:
        startproject(name="x", directory="a", dest="b", use_postgres=False)

    assert excinfo.value.exit_code == 2
    assert not (tmp_path / "a").exists()
    assert not (tmp_path / "b").exists()


def test_the_same_directory_twice_is_allowed(tmp_path, monkeypatch):
    """Redundant, but not a contradiction — nothing to refuse."""
    monkeypatch.chdir(tmp_path)

    startproject(name="x", directory="same", dest="same", use_postgres=False)

    assert (tmp_path / "same" / "pyproject.toml").is_file()


def test_the_directory_receives_the_files_directly(tmp_path, monkeypatch):
    """No extra folder named after the project nested inside it."""
    monkeypatch.chdir(tmp_path)

    startproject(name="myblog", directory="blog_folder", dest=None, use_postgres=False)

    assert (tmp_path / "blog_folder" / "pyproject.toml").is_file()
    assert not (tmp_path / "blog_folder" / "myblog").exists()


def test_without_a_directory_it_uses_the_project_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    startproject(name="myblog", directory=None, dest=None, use_postgres=False)

    assert (tmp_path / "myblog" / "pyproject.toml").is_file()


# ─── Installing dependencies ──────────────────────────────────────────────────

def test_the_installer_is_chosen_from_what_is_available():
    """uv when present, otherwise a venv and pip — never an instruction to
    install a tool the machine does not have."""
    import inspect

    from buraq.management.cli import _install_dependencies

    source = inspect.getsource(_install_dependencies)

    assert "_find_uv()" in source
    assert '"-m", "venv"' in source
    assert '"install", "buraq"' in source


def test_installing_is_opt_in():
    """Whoever ran startproject already has an environment with Buraq in it.

    Building a second one inside the project was a guess about which environment
    they meant -- not the container, not the conda env, not the one they were
    standing in. --install is there for anyone who does want it.
    """
    assert "install" in _params()
    assert "no_install" not in _params()


def test_a_failed_install_does_not_raise(tmp_path, monkeypatch):
    """
    The files are correct whatever the network did; scaffolding must not report
    failure because an index was unreachable.
    """
    import subprocess

    import buraq.management.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: None)
    monkeypatch.setattr(
        cli.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1)
    )

    assert cli._install_dependencies(tmp_path) is False


def test_a_successful_install_reports_ready(tmp_path, monkeypatch):
    import subprocess

    import buraq.management.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "uv")
    monkeypatch.setattr(
        cli.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0)
    )

    assert cli._install_dependencies(tmp_path) is True


def test_uv_is_found_beside_the_interpreter(tmp_path, monkeypatch):
    """
    `pip install "buraq[uv]"` puts uv in the same Scripts/bin directory as the
    buraq console script, which is not on PATH unless the environment is
    activated. Looking only at PATH made the extra useless unactivated.
    """
    import os

    import buraq.management.cli as cli

    bin_dir = tmp_path / "Scripts" if os.name == "nt" else tmp_path / "bin"
    bin_dir.mkdir()
    fake_uv = bin_dir / ("uv.exe" if os.name == "nt" else "uv")
    fake_uv.write_text("", encoding="utf-8")

    monkeypatch.setattr(cli.shutil, "which", lambda _: None)
    monkeypatch.setattr(cli.sys, "executable", str(bin_dir / "python"))

    assert cli._find_uv() == str(fake_uv)


def test_path_wins_when_uv_is_on_it(monkeypatch):
    import buraq.management.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/uv")

    assert cli._find_uv() == "/usr/bin/uv"


def test_no_uv_anywhere_returns_nothing(tmp_path, monkeypatch):
    import buraq.management.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _: None)
    monkeypatch.setattr(cli.sys, "executable", str(tmp_path / "python"))

    assert cli._find_uv() is None


def test_the_uv_extra_is_declared():
    """Documented as `pip install "buraq[uv]"`; it has to exist."""
    import tomllib
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    extras = data["project"]["optional-dependencies"]

    assert "uv" in extras
    assert any(spec.startswith("uv") for spec in extras["uv"])
