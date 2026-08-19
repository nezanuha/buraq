---
title: "Migrations"
description: "Buraq uses Alembic for migrations — the standard SQLAlchemy migration tool."
---

Buraq uses [Alembic](https://alembic.sqlalchemy.org/) for migrations — the standard SQLAlchemy migration tool.

## Workflow

```bash
# 1. After changing models, generate a migration
buraq makemigrations

# With a description
buraq makemigrations "add slug to post"

# 2. Apply migrations
buraq migrate

# 3. Roll back one migration
buraq rollback

# Roll back N migrations
buraq rollback 3

# 4. Check migration history
buraq showmigrations
```

## How it works

`makemigrations` runs `alembic revision --autogenerate`, which compares your model definitions to the current database schema and generates a migration file in `alembic/versions/`.

The argument is the migration's **description**, not an app. It becomes part of the
revision filename — `buraq makemigrations initial` produces something like
`622dec772435_initial.py`.

:::caution[Coming from Django]
There `makemigrations <app_label>` limits the run to one app. Buraq keeps a single
migration history for the whole project, so there is nothing to scope to and the
argument is used as the description instead. `buraq makemigrations posts` therefore
creates a migration *described* "posts" that contains every pending change; the
command warns when the text matches an installed app.
:::

`migrate` runs `alembic upgrade head`, applying all pending migrations.

## First migration

A new project has no migrations yet, so start by generating one:

```bash
buraq makemigrations initial
buraq migrate
```

`migrate` on its own only records the (empty) migration history — it does not
create tables that no migration describes.

## When nothing has changed

Autogeneration always writes a revision file, even an empty one. Buraq discards
those and tells you instead:

```bash
buraq makemigrations
# No changes detected - no migration created.
```

If the database is behind the migrations already on disk, autogenerate refuses to
run — comparing against a stale schema would generate the pending changes a second
time. Apply them first with `buraq migrate`.

## Buraq's own migrations

Buraq's contrib apps own tables — `buraq.contrib.auth` alone defines six — and
they ship their migrations inside the package rather than expecting each project
to generate them. Every app gets its own Alembic branch, applied only when the
app is in `INSTALLED_APPS`:

```ini title="alembic.ini"
path_separator = newline
version_locations =
    %(here)s/alembic/versions
    buraq.contrib.auth:migrations/versions
```

The first path is yours. The rest are resolved against the installed package, so
nothing is copied into your project and upgrading Buraq brings any schema change
with it — `buraq migrate` applies it like any other migration.

Add a line when you install another contrib app that owns tables
(`contenttypes`, `flatpages`, `redirects`, `sites`). Leaving it out means that
app's tables are never created; that is deliberate, since an app you have not
installed should not add tables to your database.

:::note[Why `path_separator = newline`]
Alembic's default is `os`, which means `;` on Windows and `:` elsewhere — an
`alembic.ini` written on one would not parse on the other. Listing one path per
line is portable and survives directory names containing spaces.
:::

Because there is now more than one branch, `buraq migrate` targets `heads`
rather than `head`, and `buraq makemigrations` writes into your own directory on
your own branch.

## What autogeneration leaves alone

Some tables are deliberately invisible to autogeneration, because a table it cannot
see in your models is one it would otherwise drop:

- models declaring [`Meta.managed = False`](/docs/topics/orm/models) — existing
  tables or database views maintained outside the ORM
- the tables the database cache and session backends create with raw SQL
  (`CACHE_TABLE` and `buraq_sessions`)
- the framework's own tables, whose migrations ship with Buraq (above)

This is the `include_object` filter in `alembic/env.py`, which calls
`buraq.core.db.tables_migrations_ignore()`.

## Manual migrations

For complex changes (data migrations, custom SQL), edit the generated migration file directly:

```python title="alembic/versions/001_add_slug.py"
def upgrade() -> None:
    op.add_column("posts", sa.Column("slug", sa.String(200), nullable=True))
    # custom data migration
    op.execute("UPDATE posts SET slug = LOWER(REPLACE(title, ' ', '-'))")
    op.alter_column("posts", "slug", nullable=False)


def downgrade() -> None:
    op.drop_column("posts", "slug")
```

## Alembic configuration

The `alembic.ini` and `alembic/env.py` files are pre-configured by `startproject`.
`env.py` reads `DATABASE_URL` from your Buraq settings automatically.

It also calls `buraq.apps.configure()`, which loads your settings module and imports
every installed app's `models`. Alembic runs in its own process, where nothing else
has configured Buraq — without that call `Base.metadata` would be empty and
autogeneration would find nothing to create.

```python title="alembic/env.py"
from buraq.apps import configure

configure()
```

Adding an app to `INSTALLED_APPS` is therefore enough for its models to be picked
up; there is no separate list of imports to maintain.
