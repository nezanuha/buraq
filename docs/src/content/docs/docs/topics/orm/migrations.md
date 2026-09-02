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

`makemigrations` runs `alembic revision --autogenerate`, which compares your model definitions to the current database schema and generates a migration file in the owning app's `migrations/` directory — the app whose models the change belongs to.

The argument is the migration's **description**, not an app. It becomes part of the
revision filename — `buraq makemigrations initial` produces something like
`622dec772435_initial.py`.

:::caution[Coming from Django]
There `makemigrations <app_label>` limits the run to one app; here the argument is
the description and `--app` does the scoping. Otherwise the model is the same — each
app owns its migrations, and the
argument is used as the description instead. `buraq makemigrations posts` therefore
creates a migration *described* "posts" that contains every pending change; the
command warns when the text matches an installed app.
:::

`migrate` runs `alembic upgrade head`, applying all pending migrations.

## First migration

A new project already has migrations — the ones Buraq ships for its own contrib
apps — but none for your models yet. Apply those first, then generate yours:

```bash
buraq migrate                    # apply the migrations Buraq ships
buraq makemigrations initial     # generate one for your models
buraq migrate                    # apply it
```

The first `migrate` matters: autogeneration compares your models against the
database and refuses to run while the database is behind, and a new project
starts behind. After this first run the usual two steps apply.

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

There is no `alembic.ini`. Where to look for migrations is derived from
`INSTALLED_APPS` — every installed app that has a `migrations` package
contributes one location, resolved as a package path so your own apps and
Buraq's are found the same way:

```python
>>> from buraq.db.migrations import version_locations
>>> version_locations()
["blog:migrations", "buraq.contrib.auth:migrations"]
```

Nothing is copied into your project, so upgrading Buraq brings any schema change
with it and `buraq migrate` applies it like any other migration. Installing
another contrib app that owns tables (`contenttypes`, `flatpages`, `redirects`,
`sites`) is enough on its own; an app you have not installed adds no tables,
which is deliberate.

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

This is the `include_object` filter in `buraq.db.migrations`, which calls
`buraq.core.db.tables_migrations_ignore()`.

## Manual migrations

For complex changes (data migrations, custom SQL), edit the generated migration file directly:

```python title="blog/migrations/001_add_slug.py"
def upgrade() -> None:
    op.add_column("posts", sa.Column("slug", sa.String(200), nullable=True))
    # custom data migration
    op.execute("UPDATE posts SET slug = LOWER(REPLACE(title, ' ', '-'))")
    op.alter_column("posts", "slug", nullable=False)


def downgrade() -> None:
    op.drop_column("posts", "slug")
```

## Alembic configuration

There is none to write. A project has no `alembic.ini` and no `alembic/`
directory: the configuration is built when a migration command runs, from the
settings you already have. `DATABASE_URL` gives the database and `INSTALLED_APPS`
gives the migration locations, so there is no second copy of either to keep in
step.

Before anything is read, `buraq.apps.configure()` loads your settings module and
imports every installed app's `models` — without it `Base.metadata` would be
empty and autogeneration would find nothing to create.

Adding an app to `INSTALLED_APPS` is therefore the only step: its models are
picked up, and its `migrations` package is searched. There is no list of imports
and no list of paths to maintain.
