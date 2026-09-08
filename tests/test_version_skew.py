"""
A project records which Buraq built it; the environment is filled separately.

`startproject` writes its own version into the new project's pyproject.toml as
a floor. Nothing then guarantees the environment agrees: `uv sync` resolves that
floor from the index, and the index is behind whatever is scaffolding whenever a
release is pending. A project made by one Buraq and run by an older one failed
with errors that pointed everywhere but at the cause -- a missing `alembic.ini`,
and an instruction to run a command that would not have helped.
"""

import pytest

from buraq.management.cli import _version_parts, _warn_if_older_than_the_project_needs


def _project(tmp_path, floor):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\n'
        'name = "myblog"\n'
        'version = "0.1.0"\n'
        'dependencies = [\n'
        f'    "buraq>={floor}",\n'
        '    "aiosqlite>=0.20.0",\n'
        ']\n',
        encoding="utf-8",
    )


# ─── Ordering ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("older", "newer"),
    [
        ("1.6.0", "1.7.0"),
        ("1.6.0", "1.6.1"),
        ("1.9.0", "1.10.0"),   # not a string comparison
        ("2.0.0", "10.0.0"),
    ],
)
def test_releases_order_by_number(older, newer):
    assert _version_parts(older) < _version_parts(newer)


def test_a_prerelease_suffix_does_not_break_the_read():
    assert _version_parts("1.7.0rc1") == (1, 7, 0)
    assert _version_parts("1.7.0.dev3") == (1, 7, 0)


def test_something_unreadable_orders_below_everything():
    """It must never invent a mismatch out of a version it cannot parse."""
    assert _version_parts("") == ()
    assert _version_parts("not-a-version") == ()


# ─── The warning ──────────────────────────────────────────────────────────────

def test_an_older_buraq_in_a_newer_project_is_named(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _project(tmp_path, "9.9.0")

    _warn_if_older_than_the_project_needs()

    out = capsys.readouterr().out
    assert "9.9.0" in out, "the version the project asks for has to be in the message"


def test_a_matching_buraq_says_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _project(tmp_path, "0.1.0")

    _warn_if_older_than_the_project_needs()

    assert capsys.readouterr().out == ""


def test_nothing_is_said_outside_a_project(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    _warn_if_older_than_the_project_needs()

    assert capsys.readouterr().out == ""


def test_a_pyproject_without_buraq_is_left_alone(tmp_path, monkeypatch, capsys):
    """Someone else's project that happens to be the working directory."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "other"\ndependencies = ["httpx"]\n', encoding="utf-8"
    )

    _warn_if_older_than_the_project_needs()

    assert capsys.readouterr().out == ""


def test_an_unreadable_pyproject_is_not_this_command_s_problem(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text("this is not toml [[[", encoding="utf-8")

    _warn_if_older_than_the_project_needs()

    assert capsys.readouterr().out == ""


def test_it_warns_rather_than_stopping(tmp_path, monkeypatch):
    """
    A newer project on an older Buraq usually works. Being wrong about the
    mismatch must not stop anybody working.
    """
    import typer

    monkeypatch.chdir(tmp_path)
    _project(tmp_path, "9.9.0")

    try:
        _warn_if_older_than_the_project_needs()
    except typer.Exit:  # pragma: no cover - the failure this guards against
        pytest.fail("the check must not exit")


# ─── The floor startproject writes ────────────────────────────────────────────

def test_the_floor_written_is_the_version_doing_the_scaffolding(tmp_path, monkeypatch):
    """
    This is what makes the mismatch impossible rather than merely visible: a
    project scaffolded by an unreleased build declares a version the index
    cannot supply, so `uv sync` fails outright instead of quietly installing
    the last release in its place.
    """
    import buraq
    from buraq.management.cli import startproject

    monkeypatch.chdir(tmp_path)
    startproject(
        name="myblog", directory="myblog", dest=None, use_postgres=False, install=False
    )

    written = (tmp_path / "myblog" / "pyproject.toml").read_text(encoding="utf-8")

    assert f'"buraq>={buraq.__version__}"' in written
