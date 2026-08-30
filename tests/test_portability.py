"""
Behaviour that must not depend on the machine it runs on.

Python's text file APIs default to the *locale* encoding, which differs across
the environments Buraq is expected to run in: UTF-8 on most Linux and macOS
setups, cp1252 on a typical Windows install, and plain ASCII under the POSIX
locale that minimal container images default to. Anything written or read
without an explicit encoding therefore behaves differently per platform.

Scaffolding made that concrete: `startproject` wrote a `main.py` containing an
em dash using the locale encoding, so on Windows the file landed as cp1252 while
Python reads source as UTF-8 -- the generated project failed to start with
"Non-UTF-8 code starting with '\x97'".
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "buraq"


def _calls_without_encoding(path: Path):
    """Yield (lineno, method) for text file IO that relies on the locale."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("write_text", "read_text")
            and not any(kw.arg == "encoding" for kw in node.keywords)
        ):
            yield node.lineno, node.func.attr


def test_no_text_file_io_relies_on_the_locale_encoding():
    offenders = [
        f"{path.relative_to(PACKAGE.parent)}:{lineno} ({attr})"
        for path in sorted(PACKAGE.rglob("*.py"))
        for lineno, attr in _calls_without_encoding(path)
    ]

    assert offenders == [], "pass encoding='utf-8' explicitly:\n" + "\n".join(offenders)


def _scaffolded_files():
    """Render each file `startproject` writes, with the encoding it uses."""
    tree = ast.parse((PACKAGE / "management" / "cli.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "write_text"
            and node.args
        ):
            continue
        try:
            content = ast.literal_eval(node.args[0])
        except (ValueError, TypeError):
            continue  # f-string or variable; not a static template
        encoding = next(
            (ast.literal_eval(kw.value) for kw in node.keywords if kw.arg == "encoding"),
            None,
        )
        name = ast.unparse(node.func.value).split("/")[-1].strip(" \"'")
        yield name, content, encoding


def test_every_scaffolded_file_is_written_as_utf8():
    wrong = [name for name, _, encoding in _scaffolded_files() if encoding != "utf-8"]

    assert wrong == [], f"scaffolded without encoding='utf-8': {wrong}"


@pytest.mark.parametrize(
    "name,content,encoding",
    [pytest.param(*f, id=f[0]) for f in _scaffolded_files() if f[0].endswith(".py")],
)
def test_scaffolded_python_files_load(name, content, encoding, tmp_path):
    """
    Written with the locale encoding, a template containing any non-ASCII
    character produced a file the interpreter refused to parse.
    """
    path = tmp_path / name
    path.write_text(content, encoding=encoding)

    result = subprocess.run(
        [sys.executable, "-c", f"compile(open({str(path)!r}, 'rb').read(), 'm', 'exec')"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_the_scaffolded_manage_py_runs_in_place():
    """It no longer re-executes itself, so it cannot detach or pick the wrong venv.

    manage.py used to look for a .venv beside it and re-run itself with that
    interpreter, which needed one branch to avoid orphaning the server on
    Windows and another to identify the environment on POSIX -- where the venv's
    python is a symlink to the system one and comparing resolved paths said they
    were the same. The project no longer creates an environment, so there is
    nothing to re-enter and none of that has to be right.
    """
    manage = next(c for name, c, _ in _scaffolded_files() if name == "manage.py")

    for absent in ("os.execv", "subprocess", "_bootstrap", ".venv", "sys.prefix"):
        assert absent not in manage, f"manage.py should no longer mention {absent}"
    assert "from buraq.management.cli import main" in manage


def test_startproject_does_not_read_from_stdin():
    """
    Confirming a prompt against a closed stdin aborted with exit 1 on a project
    that had been created, so `buraq startproject x && cd x` failed in scripts
    and CI. Scaffolding should not depend on someone being there to answer.
    """
    source = (PACKAGE / "management" / "cli.py").read_text(encoding="utf-8")
    start = source.index("def startproject(")
    end = source.index("\n@app.command()", start)
    body = source[start:end]

    assert "typer.confirm" not in body
    assert "typer.prompt" not in body


def test_startproject_next_steps_do_not_set_up_an_environment():
    """Reaching startproject means an environment already works.

    The command printed a setup step -- uv sync, or venv and pip -- which told
    the reader to do what running the command had just proved they had done.
    What it prints now is only what is actually outstanding.
    """
    source = (PACKAGE / "management" / "cli.py").read_text(encoding="utf-8")
    start = source.index("def startproject(")
    end = source.index(chr(10) + "@app.command()", start)
    printed = chr(10).join(
        line for line in source[start:end].splitlines() if "typer.echo(" in line
    )

    for absent in ("uv sync", "python -m venv", "pip install buraq"):
        assert absent not in printed, f"next steps should not print {absent!r}"
    assert "buraq migrate" in printed
    assert "buraq runserver" in printed
