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


# ─── Scaffolding into a directory that already exists ─────────────────────────
#
# Every existing directory used to be refused, which made the ordinary layout
# unreachable: .venv cannot live inside a project you are not allowed to
# scaffold into, and the environment has to exist before `buraq` does. So the
# venv landed beside the project instead of in it. What actually matters is not
# overwriting anything, and that is what is checked now.

def test_an_existing_empty_directory_is_accepted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "myblog").mkdir()

    startproject(
        name="myblog", directory="myblog", dest=None, use_postgres=False, install=False
    )

    assert (tmp_path / "myblog" / "pyproject.toml").is_file()


def test_a_directory_holding_only_an_environment_is_accepted(tmp_path, monkeypatch):
    """The layout this exists for: venv first, project scaffolded around it."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".git").mkdir()

    startproject(
        name="myblog", directory=".", dest=None, use_postgres=False, install=False
    )

    assert (tmp_path / "pyproject.toml").is_file()
    assert (tmp_path / ".venv").is_dir(), "the environment must survive"


@pytest.mark.parametrize("existing", ["pyproject.toml", "main.py", "config", "tests"])
def test_a_file_that_would_be_overwritten_stops_the_command(
    existing, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "myblog"
    target.mkdir()
    if "." in existing:
        (target / existing).write_text("mine", encoding="utf-8")
    else:
        (target / existing).mkdir()

    with pytest.raises(typer.Exit) as excinfo:
        startproject(
            name="myblog", directory="myblog", dest=None, use_postgres=False,
            install=False,
        )

    assert excinfo.value.exit_code == 1
    assert not (target / "manage.py").exists(), "nothing may be written on refusal"


def test_the_refusal_names_what_is_in_the_way(tmp_path, monkeypatch, capsys):
    """"Directory already exists" did not say which file to move."""
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "myblog"
    target.mkdir()
    (target / "main.py").write_text("mine", encoding="utf-8")

    with pytest.raises(typer.Exit):
        startproject(
            name="myblog", directory="myblog", dest=None, use_postgres=False,
            install=False,
        )

    assert "main.py" in capsys.readouterr().err


def test_a_path_that_is_a_file_is_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "myblog").write_text("not a directory", encoding="utf-8")

    with pytest.raises(typer.Exit) as excinfo:
        startproject(
            name="myblog", directory="myblog", dest=None, use_postgres=False,
            install=False,
        )

    assert excinfo.value.exit_code == 1


def test_scaffolding_in_place_does_not_print_cd(tmp_path, monkeypatch, capsys):
    """`cd .` reads as a step the reader has missed."""
    monkeypatch.chdir(tmp_path)

    startproject(
        name="myblog", directory=".", dest=None, use_postgres=False, install=False
    )

    assert "cd ." not in capsys.readouterr().out


def test_every_written_top_level_entry_is_declared(tmp_path, monkeypatch):
    """
    The collision check is a hand-written list beside the code that writes the
    files. A new file added to the scaffold without a line here would silently
    become one this command overwrites without warning.
    """
    from buraq.management.cli import _SCAFFOLD_ENTRIES

    monkeypatch.chdir(tmp_path)
    startproject(
        name="myblog", directory="out", dest=None, use_postgres=False, install=False
    )

    written = {p.name for p in (tmp_path / "out").iterdir()}

    assert written <= set(_SCAFFOLD_ENTRIES), (
        f"not declared in _SCAFFOLD_ENTRIES: {sorted(written - set(_SCAFFOLD_ENTRIES))}"
    )


# ─── The environment step in the closing output ───────────────────────────────
#
# It used to be left out on the grounds that whoever ran the command already had
# Buraq importable. True, but importable from wherever `buraq` was installed --
# and once that is a tool install, following the output left you in a project
# with no environment of its own.

def test_the_closing_output_names_the_environment_step(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    startproject(
        name="myblog", directory="myblog", dest=None, use_postgres=False, install=False
    )

    out = capsys.readouterr().out
    assert "activate" in out
    assert out.index("activate") < out.index("buraq migrate"), (
        "the environment has to be built before the commands that use it"
    )


def test_a_project_that_already_has_an_environment_is_not_told_to_make_one(
    tmp_path, monkeypatch, capsys
):
    """A container, a conda env, or --install having just built one."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".venv").mkdir()

    startproject(
        name="myblog", directory=".", dest=None, use_postgres=False, install=False
    )

    out = capsys.readouterr().out
    assert "activate" not in out
    assert "buraq migrate" in out


def test_the_environment_step_matches_the_installer_available(
    tmp_path, monkeypatch, capsys
):
    """uv sync where uv is, venv + pip where it is not — never an instruction
    to use a tool the machine does not have."""
    import buraq.management.cli as cli

    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/uv")
    startproject(
        name="a", directory="a", dest=None, use_postgres=False, install=False
    )
    with_uv = capsys.readouterr().out

    monkeypatch.setattr(cli.shutil, "which", lambda _: None)
    monkeypatch.setattr(cli.sys, "executable", str(tmp_path / "python"))
    startproject(
        name="b", directory="b", dest=None, use_postgres=False, install=False
    )
    without_uv = capsys.readouterr().out

    assert "uv sync" in with_uv
    assert "pip install" not in with_uv

    assert "uv sync" not in without_uv
    assert "-m venv .venv" in without_uv
    assert "pip install buraq" in without_uv


def test_the_activate_line_is_a_path_not_an_escape(tmp_path, monkeypatch, capsys):
    r"""`"\Scripts\activate"` in a plain string makes \a a BEL character."""
    monkeypatch.chdir(tmp_path)

    startproject(
        name="myblog", directory="myblog", dest=None, use_postgres=False, install=False
    )

    assert "\a" not in capsys.readouterr().out
