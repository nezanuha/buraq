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
