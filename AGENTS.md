# AGENTS.md

Guidance for AI coding agents working in this repository.
Human contributor setup lives in [CONTRIBUTING.md](CONTRIBUTING.md) — this file
covers what is easy to get wrong here.

## Architecture: async-first, with no sync layer

Buraq is the mirror image of Django. Django is sync at its core with async
adapters; Buraq is async at its core with **no synchronous implementation
underneath**. Do not add one.

- **Every database call is `await`-only.** There is no sync ORM path. A
  `QuerySet` is lazy and not iterable — it must be awaited.
- **`render()` is a coroutine.** Always `return await render(request, ...)`.
  It is async because context processors may query the database.
- **Never add `sync_to_async` / `async_to_sync` or an `asgiref` dependency.**
  The standard library covers both directions: `asyncio.to_thread()` to call
  blocking code from async, `asyncio.run()` outside the request cycle.
- **Never call `asyncio.run()` inside a request.** A running loop cannot be
  nested, and per-call loops fragment the connection pool.
- **Blocking work goes through `await asyncio.to_thread(...)`.** See
  `buraq/contrib/auth/backends.py` for the house pattern.
- **Extension points accept sync or async callables** and detect which at call
  time — signals, form validators, `on_commit()` callbacks, background tasks,
  sitemap `items()`, context processors. Preserve that when touching them.

Full explanation: `docs/topics/sync-and-async`.

## Commands

```bash
uv sync                        # install
uv run pytest                  # tests (hermetic — tests/conftest.py sets env)
uv run ruff check buraq/       # lint; must be clean before pushing
uv run ruff format buraq/
```

Tests must not require a `.env`, a live database, or network access.

## Built-in UI stylesheet

The stylesheet for the bundled admin panel and debug error page is built with
Tailwind + Frutjam from `assets/`, and the **output is committed** — you only
need this when changing `assets/input.css`:

```bash
cd assets
npm install
npm run build     # -> buraq/contrib/admin/static/admin/frutjam.min.css
```

`input.css` declares `@source "../"` deliberately. Tailwind v4 auto-detects
sources from the nearest package root; without that line the scan would cover
only `assets/` and silently drop ~20 KB of styles. Do not narrow it without
diffing the generated CSS byte-for-byte.

## Documentation

Docs are an Astro + Starlight site in `docs/`, not in this package.

```bash
cd docs
npm run build                  # must pass before shipping doc changes
node scripts/scan-mdx-hazards.mjs
```

- Pages live in `src/content/docs/docs/`, served under `/docs/...`.
- `.mdx` files treat `{` and `<` as syntax — wrap Jinja (`{% ... %}`) in
  backticks or the build fails. The hazard scanner catches these.
- Changing a public API means updating the examples in the docs too.
- Before starting docs for a new major version, read
  `docs/README.md` — the current docs must be snapshotted first.

## Conventions

- **Never commit a personal email address.** Use `security@buraqproject.com`.
- **Do not name Django in CHANGELOG entries.**
- Add tests for new behaviour; the ORM is under-covered, so err toward more.
- Match the surrounding style: module docstrings with a `Usage::` block,
  numbered section comments in long functions.

## Landmines

- `buraq/orm/base.py` — `Model.__init_subclass__` runs for **every** model in
  the framework and in user projects. Changes here are high blast radius.
- Field objects are converted to SQLAlchemy `Column`s partway through that
  method; anything needing field metadata (`_to`, `related_name`) must capture
  it *before* that point.
- `buraq/management/cli.py` contains the code templates `startproject` and
  `startapp` scaffold. Changing a public API means updating those strings too,
  or every new project is generated broken.
