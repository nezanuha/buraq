# Contributing to Buraq

## Setup

```bash
git clone https://github.com/nezanuha/buraq
cd buraq
uv sync
```

## Running tests

```bash
uv run pytest
```

## Linting

```bash
uv run ruff check buraq/
uv run ruff format buraq/
```

## Pull Request Guidelines

- One feature or fix per PR
- Add tests for any new behaviour
- All existing tests must pass
- Run ruff before pushing

## Reporting Bugs

Open a GitHub issue with:
- Python version
- Buraq version
- Minimal reproduction case
- Expected vs actual behaviour

## Security

See [SECURITY.md](SECURITY.md) — do not open public issues for vulnerabilities.
