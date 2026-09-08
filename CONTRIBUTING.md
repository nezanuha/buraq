# Contributing to Buraq

## Setup

```bash
git clone https://github.com/nezanuha/buraq
cd buraq
uv sync
```

Buraq supports **Python 3.11 to 3.13** — CI runs every one of them on Linux,
macOS and Windows, so a change that only works on your version will fail there.

## Before you push

Four gates. The first three are what CI runs; the fourth catches things nothing
else does.

```bash
uv run pytest                        # 1396 tests, expect no failures
uv run ruff check buraq/ tests/
uv run ruff format buraq/
uv run python scripts/audit.py       # public API vs docs, exports, duplicates
```

`scripts/audit.py` checks that every public symbol is documented, exported and
not defined twice. Add `--fail` to make it exit non-zero, which is what you want
in a script. It is **not** part of CI, so nothing will catch these for you.

Mypy is configured in `pyproject.toml` and is **not** a gate: the codebase does
not satisfy `strict = true` yet, so running it reports thousands of errors that
are not your change. Do not treat it as a check to pass.

## Documentation

The site is Astro + Starlight under `docs/`. Its build runs six content checks —
empty icons, plaintext code fallbacks, unrendered MDX expressions, unscoped
`#_top` rules, missing asset references and stray control characters — and the
deploy uses the same command, so a page that fails here does not ship:

```bash
cd docs
npm ci
npm run build
```

Documentation deploys on its own, when `docs/**` changes, rather than waiting for
a release. It will refuse to publish while `pyproject.toml` names a version that
is not on PyPI, so that a page never describes behaviour nobody can install.

## The changelog

Every user-visible change needs an entry under `## [Unreleased]` in
`CHANGELOG.md`, in one of the six [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
sections: Added, Changed, Deprecated, Removed, Fixed, Security. Do not invent
others — the release workflow reads this file to build the GitHub release notes,
and it fails outright when a version has no section.

## Trying a scaffolded project against your build

`buraq startproject` writes its own version into the new project's
`pyproject.toml` as a floor, so a project made by an unreleased build declares a
Buraq that is not on PyPI yet. `uv sync` inside it therefore fails, and it
should — before that floor existed, uv quietly resolved the last released
version instead, giving a project scaffolded by one Buraq and run by another.
That mismatch surfaced as errors pointing anywhere but at the cause.

Install your build into the project instead of resolving from the index:

```bash
buraq startproject myproject
cd myproject

uv venv
uv pip install -e /path/to/buraq      # your working tree, not PyPI

source .venv/bin/activate             # Windows: .venv\Scripts\activate
buraq migrate
buraq runserver
```

Check which Buraq a project is actually running at any point:

```bash
buraq shell -c "import buraq; print(buraq.__file__, buraq.__version__)"
```

A path under your working tree is what you want. A path under `site-packages`
with a released version number means the project is running a different Buraq
from the one you are changing.

## Pull Request Guidelines

- One feature or fix per PR
- Add tests for any new behaviour
- All four gates above pass
- A changelog entry under `## [Unreleased]`

## Reporting Bugs

Open a GitHub issue with:
- Python version
- Buraq version
- Minimal reproduction case
- Expected vs actual behaviour

## Security

See [SECURITY.md](SECURITY.md) — do not open public issues for vulnerabilities.
