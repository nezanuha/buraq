# Migrations

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

`migrate` runs `alembic upgrade head`, applying all pending migrations.

## First migration

For a new project, running `buraq migrate` automatically creates all tables defined in your models — no migration file needed for the initial setup.

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

The `alembic.ini` and `alembic/env.py` files are pre-configured by `startproject`. The `env.py` reads `DATABASE_URL` from your Buraq settings automatically.
