"""
The `buraq` console script re-executes using the project's virtualenv.

The script is installed inside whichever environment Buraq was installed into.
Installed globally — which you need for `buraq startproject` to work anywhere —
it would otherwise run a project's commands against that global environment
instead of the project's own, silently using the wrong dependency set.

`_bootstrap_cli()` runs before the rest of the package is imported and swaps the
interpreter. These tests cover when it must stay out of the way; the swap itself
replaces the process, so it is exercised through a subprocess.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

import buraq

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(code: str, *, cwd: Path, argv0: str, env_extra: dict | None = None):
    """Run `code` in a subprocess with sys.argv[0] spoofed to `argv0`."""
    env = {**os.environ, "SECRET_KEY": "bootstrap-test-key", **(env_extra or {})}
    prelude = f"import sys; sys.argv = [{argv0!r}]; sys.path.insert(0, {str(REPO_ROOT)!r})\n"
    return subprocess.run(
        [sys.executable, "-c", prelude + code],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_plain_import_never_reexecutes(tmp_path):
    """`import buraq` in application code must be left alone."""
    (tmp_path / ".venv").mkdir()

    result = _run(
        "import buraq; print('IMPORTED', sys.executable)",
        cwd=tmp_path,
        argv0="pytest",  # not the console script
    )

    assert "IMPORTED" in result.stdout
    assert sys.executable in result.stdout


def test_no_reexec_without_a_project_venv(tmp_path):
    """Nothing to switch to — the command must run as-is rather than fail."""
    result = _run(
        "import buraq; print('IMPORTED')",
        cwd=tmp_path,  # no .venv here
        argv0="buraq",
    )

    assert "IMPORTED" in result.stdout


def test_escape_hatch_disables_the_swap(tmp_path):
    (tmp_path / ".venv").mkdir()

    result = _run(
        "import buraq; print('IMPORTED')",
        cwd=tmp_path,
        argv0="buraq",
        env_extra={"BURAQ_NO_BOOTSTRAP": "1"},
    )

    assert "IMPORTED" in result.stdout


def test_no_reexec_when_already_on_the_project_interpreter():
    """Running from the repo, sys.executable already is ./.venv — must not loop."""
    result = _run(
        "import buraq; print('IMPORTED')",
        cwd=REPO_ROOT,
        argv0="buraq",
    )

    assert "IMPORTED" in result.stdout
    assert result.returncode == 0


def test_bootstrap_is_defined_before_the_package_imports():
    """
    The swap has to happen before settings are validated, so it must be the
    first thing in buraq/__init__.py.
    """
    source = (REPO_ROOT / "buraq" / "__init__.py").read_text(encoding="utf-8")
    bootstrap_at = source.index("def _bootstrap_cli")
    first_import = source.index("from buraq import")

    assert bootstrap_at < first_import


@pytest.mark.parametrize("attr", ["__version__"])
def test_version_tracks_package_metadata(attr):
    """__version__ was hardcoded to 0.1.0 while the package shipped 1.5.x."""
    from importlib.metadata import version

    assert getattr(buraq, attr) == version("buraq")


def test_windows_keeps_the_parent_attached():
    """
    Windows has no real exec: os.execv() spawns a child and exits the parent, so
    the shell returns its prompt while the server keeps running detached and
    Ctrl+C reaches nobody. On nt the bootstrap must run a child and propagate
    its exit code instead.
    """
    source = (REPO_ROOT / "buraq" / "__init__.py").read_text(encoding="utf-8")

    assert "os.name == 'nt'" in source
    assert "subprocess.run(argv).returncode" in source
    # execv is still the right call everywhere else
    assert "os.execv(str(python), argv)" in source


def test_exit_code_is_propagated_through_the_bootstrap(tmp_path):
    """A failing command must not report success just because it was re-executed."""
    (tmp_path / ".venv").mkdir()

    result = _run(
        "import buraq, sys; sys.exit(3)",
        cwd=tmp_path,      # no usable interpreter in that .venv, so no re-exec
        argv0="buraq",
    )

    assert result.returncode == 3


def test_version_flag_and_module_form_both_work(tmp_path):
    """
    The install guide points at both: `buraq --version` to check the install, and
    `python -m buraq` when the console script is not on PATH. Neither existed.
    """
    env = {**os.environ, "SECRET_KEY": "version-check-key"}
    env["PYTHONPATH"] = str(REPO_ROOT)

    for args in (["-m", "buraq", "--version"], ["-m", "buraq", "-V"]):
        result = subprocess.run(
            [sys.executable, *args],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        assert "Buraq" in result.stdout, result.stdout


def test_the_module_entry_point_exists():
    """`python -m buraq` needs a __main__, or it reports the package is not runnable."""
    assert (REPO_ROOT / "buraq" / "__main__.py").is_file()
