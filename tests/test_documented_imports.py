"""
Every `from buraq… import X` in the documentation has to actually import.

A line somebody copies is the one place a wrong module path costs the most, and
these rot silently: the code moves, the page does not, and nothing fails until a
reader tries it. Fifteen were broken when this was first run --
`buraq.db.transaction`, `buraq.core.auth`, `buraq.contrib.ratelimit`,
`buraq.forms.forms`, `buraq.contrib.csrf.CSRFMiddleware`,
`buraq.contrib.email.get_connection` and more.
"""

import importlib
import pathlib
import re

import pytest

DOCS = pathlib.Path(__file__).resolve().parents[1] / "docs" / "src" / "content" / "docs"
IMPORT = re.compile(r"^\s*from\s+(buraq[\w.]*)\s+import\s+([^\n#]+)", re.M)


def _documented_imports():
    """(page, module, name) for every buraq import shown in the docs."""
    if not DOCS.is_dir():
        return []

    found = []
    for page in sorted(DOCS.rglob("*.md")) + sorted(DOCS.rglob("*.mdx")):
        text = page.read_text(encoding="utf-8", errors="replace")
        for module, names in IMPORT.findall(text):
            for raw in names.split(","):
                name = raw.strip().split(" as ")[0].strip().strip("()")
                if name and name.isidentifier():
                    found.append((page.relative_to(DOCS).as_posix(), module, name))
    return sorted(set(found))


CASES = _documented_imports()


@pytest.mark.skipif(not CASES, reason="documentation sources are not present")
@pytest.mark.parametrize("page,module,name", CASES, ids=lambda v: str(v)[:60])
def test_the_import_works(page, module, name):
    try:
        imported = importlib.import_module(module)
    except ImportError as exc:  # pragma: no cover - the failure message is the point
        pytest.fail(f"{page}: `from {module} import {name}` -- {exc}")

    if hasattr(imported, name):
        return

    # `from buraq.orm import functions` names a submodule, which is not an
    # attribute of the package until something imports it.
    try:
        importlib.import_module(f"{module}.{name}")
    except ImportError:
        pytest.fail(f"{page}: `from {module} import {name}` -- {module} has no {name!r}")


def test_there_are_imports_to_check():
    """A regex that matches nothing would make every case above vacuous."""
    if DOCS.is_dir():
        assert len(CASES) > 100, f"only {len(CASES)} imports found; the pattern may be wrong"
