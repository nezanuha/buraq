---
title: "Built-in Management Commands"
description: "When --settings is given, Buraq imports the named module and applies every upper-case attribute to the live settings object before the command runs. This lets…"
---

All commands run via `buraq <command>`.

## Global options

These options are accepted by every command:

| Option | Env var | Description |
|---|---|---|
| `--settings MODULE` | `BURAQ_SETTINGS_MODULE` | Dotted path to the settings module to use |

```bash
# Use production settings for a single command
buraq migrate --settings config.prod_settings

# Or set the env var once for the whole shell session
export BURAQ_SETTINGS_MODULE=config.prod_settings
buraq migrate
buraq createsuperuser
```

When `--settings` is given, Buraq imports the named module and applies every upper-case attribute to the live settings object before the command runs. This lets you keep separate settings files for development, staging, and production without changing `manage.py`.

## Server

```bash
# Start development server (default: main:app on 127.0.0.1:8000)
buraq runserver

# Custom port (Django-style)
buraq runserver 8080

# Custom host:port
buraq runserver 0.0.0.0:8080

# Custom app path
buraq runserver config.urls:app

# Options
buraq runserver --no-reload      # disable auto-reload
buraq runserver --workers 4      # multiple workers (disables reload)
```

## Database

```bash
# Generate migration from model changes
buraq makemigrations
buraq makemigrations "add slug to post"

# Apply all pending migrations
buraq migrate

# Migrate to a specific revision
buraq migrate abc1234

# Roll back migrations
buraq rollback          # 1 migration
buraq rollback 3        # 3 migrations

# View migration history
buraq showmigrations
```

## Interactive shell

```bash
# Open an interactive Python shell with models pre-imported
buraq shell

# Run a single expression and exit
buraq shell -c "print(await Post.objects.count())"
```

All model classes from `INSTALLED_APPS` and `SessionLocal` are auto-imported so you can query the database immediately.

## System checks

```bash
# Run all registered system checks
buraq check
```

Prints results grouped by severity (`INFO`, `WARNING`, `ERROR`, `CRITICAL`). Exits with code `1` if any `ERROR`-level check fails.

## Database shell

```bash
# Open the native CLI for the configured database
buraq dbshell
```

Detects the dialect from `DATABASE_URL` and launches `sqlite3`, `psql`, or `mysql` with the correct connection arguments. Requires the database CLI to be installed on `PATH`.

## Data import / export

```bash
# Dump all tables to JSON
buraq dumpdata
buraq dumpdata --output fixtures/initial.json
buraq dumpdata --indent 2
buraq dumpdata --exclude auth_user --exclude buraq_sessions

# Load a JSON fixture
buraq loaddata fixtures/initial.json
buraq loaddata fixtures/initial.json --table posts_post
```

`dumpdata` serialises every SQLAlchemy table to a JSON list. `loaddata` bulk-inserts rows; use `--table` to restrict which tables are loaded.

## Flush

```bash
# Delete all rows from every table (schema is kept)
buraq flush

# Skip the confirmation prompt
buraq flush --no-input
```

Tables are truncated in reverse dependency order to avoid FK violations. Prompts for confirmation unless `--no-input` is passed.

## Change password

```bash
buraq changepassword alice
```

Prompts for a new password (with confirmation) and updates `hashed_password` for the named user via `hash_password()`.

## Inspect database

```bash
# Print model class stubs inferred from the live schema
buraq inspectdb

# Inspect a specific table
buraq inspectdb --table posts_post

# Redirect to a file
buraq inspectdb > myapp/models.py
```

Uses SQLAlchemy's `inspect()` to read table names, column types, and constraints, then maps them to Buraq field strings.

## Diff settings

```bash
# Show settings that differ from defaults
buraq diffsettings

# Show every setting (including defaults)
buraq diffsettings --all
```

Changed settings are marked with `###` so they're easy to spot.

## Send test email

```bash
# Verify email configuration
buraq sendtestemail alice@example.com
```

Sends a plain-text test message using the configured email backend (`EMAIL_HOST`, `EMAIL_PORT`, credentials). Use this to confirm SMTP settings before deploying.

## Users

```bash
# Create a superuser (interactive — prompts for username, email, password)
buraq createsuperuser

# Pass values directly (password is still prompted if omitted)
buraq createsuperuser --username admin --email admin@example.com

# Fully non-interactive (for scripts / CI)
buraq createsuperuser --username admin --email admin@example.com --password secret --no-input
```

The interactive flow asks for username, email, and password (with a confirmation prompt). It rejects empty passwords and mismatched confirmation attempts. Exits with an error if the username or email is already taken.

## Apps & Projects

```bash
# Scaffold a new app
buraq startapp posts

# Scaffold a new project
buraq startproject myproject

# Put it somewhere other than ./myproject
buraq startproject myproject blog_folder

# --dest does the same thing, for scripts written against earlier versions
buraq startproject myproject --dest blog_folder

buraq startproject myproject --postgres    # with PostgreSQL config
```

The files land **directly** in the directory you name — no second folder is
nested inside it. Without one, the project goes in `./<name>`.

## Static files

```bash
# Collect all static files into STATIC_ROOT
buraq collectstatic

# Custom destination (overrides STATIC_ROOT)
buraq collectstatic --dest /var/www/static

# Wipe destination before collecting
buraq collectstatic --clear

# Find where a static file lives (searches STATICFILES_FINDERS)
buraq findstatic css/style.css
buraq findstatic images/logo.png --first   # stop at first match
```

Files are discovered via `STATICFILES_FINDERS` (searches `STATICFILES_DIRS` and each installed app's `static/` directory) and saved via `STATICFILES_STORAGE`. When `ManifestStaticFilesStorage` is active, content-hashed copies are written and `staticfiles.json` is generated.

Output:

```
Collecting static files into /app/staticfiles ...
Done. Copied: 24, Skipped (unchanged): 8, Post-processed: 24
```

`findstatic` prints the absolute path for each match across all finders:

```
/app/static/css/style.css
/app/myapp/static/css/style.css
```

## Cache

```bash
# Clear all cached data
buraq clearcache

# Create the database cache table (DatabaseCache backend)
buraq createcachetable
buraq createcachetable --table my_cache_table
```

## Sessions

```bash
# Delete all expired sessions from the database session table
buraq clearsessions
```

Only relevant when using `DatabaseSessionBackend`. Cookie-based sessions need no cleanup.

## Internationalization

```bash
# Extract translatable strings into .po files
buraq makemessages -l ar
buraq makemessages -l ar -l fr -l es          # multiple locales at once
buraq makemessages -l ar --domain django       # custom domain

# Compile .po files into binary .mo files
buraq compilemessages

# Custom domain
buraq compilemessages --domain django
```

Requires `babel` (`buraq install babel`). Strings are extracted from `.py` and `.html` files by default. Compiled `.mo` files are written next to the `.po` files in `locale/<lang>/LC_MESSAGES/`.

See [Internationalization](../topics/i18n.md) for full usage.

## Migrations (advanced)

```bash
# Print the SQL a migration would run without executing it
buraq sqlmigrate abc1234
buraq sqlmigrate abc1234 --backwards   # downgrade SQL

# Squash a range of migrations into one
buraq squashmigrations abc1234 head
buraq squashmigrations abc1234 head --name squashed_v2

# Merge two divergent migration heads into one
buraq optimizemigration abc1234 def5678
buraq optimizemigration abc1234 def5678 --name merge_branches

# Print the SQL that flush would run (without executing it)
buraq sqlflush

# Print SQL to reset PostgreSQL autoincrement sequences
buraq sqlsequencereset
buraq sqlsequencereset posts auth   # specific apps only
```

`sqlflush` is useful for auditing or generating a manual reset script. `sqlsequencereset` is only needed for PostgreSQL after bulk data imports that bypass the ORM.

## Test runner

```bash
# Run the test suite via pytest
buraq test
buraq test tests/
buraq test --failfast
buraq test --verbosity 2
```

`BURAQ_ENV=test` is set automatically so settings can branch on it.

## CommandError / SystemCheckError

Custom management commands raise `CommandError` to print an error message and exit with a non-zero code without a Python traceback:

```python
from buraq.management.base import CommandError

class Command(BaseCommand):
    async def handle(self, *args, **options):
        if not options["name"]:
            raise CommandError("--name is required.")
```

`SystemCheckError` is a subclass raised automatically by the `check` command when one or more registered system checks report an `ERROR`-level issue. You do not normally raise it directly.

## execute_from_command_line

`execute_from_command_line` is the entry point used by `manage.py`:

```python title="manage.py"
#!/usr/bin/env python
"""Run: python manage.py <command>"""
import os, sys
from pathlib import Path

if Path(".venv/bin/python").exists():
    os.execv(".venv/bin/python", [".venv/bin/python"] + sys.argv)

from buraq.management.cli import execute_from_command_line
execute_from_command_line(sys.argv)
```

This is generated automatically when you run `buraq startproject`.

## URL inspection

```bash
# List all registered routes (default app: main:app)
buraq listurls

# Use a specific app
buraq listurls --app config.urls:app
```

Output:

```
Path                           View                                      Name
------------------------------------------------------------------------
/                              myapp.views.home                          home
/posts                         myapp.views.post_list                     post_list
/posts/{pk}                    myapp.views.post_detail                   post_detail
/auth/login                    buraq.contrib.auth.views.LoginView        login
```

Named routes appear in the `Name` column. Unnamed routes show an empty name.

## Content types

```bash
# Remove ContentType records for models that no longer exist
buraq remove_stale_contenttypes
buraq remove_stale_contenttypes --no-input          # skip confirmation
buraq remove_stale_contenttypes --include-stale-apps  # also check still-installed apps
```

Run this after removing an app or model from `INSTALLED_APPS` to clean up orphaned rows in the `contenttypes` table. See [Content Types](../topics/contenttypes.md).

## Test server

```bash
# Load fixtures then start the development server
buraq testserver fixtures/posts.json fixtures/users.json
buraq testserver fixtures/initial.json --port 8001
buraq testserver fixtures/initial.json --no-input        # skip confirmation
buraq testserver fixtures/initial.json --app config.urls:app  # custom app path
```

Clears the database, loads the given fixture files, then starts the dev server. Useful for manual QA sessions with realistic data without touching the production database.

## Background task worker

```bash
buraq worker
buraq worker --queue high-priority --concurrency 4
buraq worker --queue email --poll-interval 0.5 --max-tasks 100
```

Polls the task backend for pending tasks and executes them. Requires `DatabaseBackend` — the `DummyBackend` executes tasks in-process and needs no worker.

| Flag | Default | Description |
|---|---|---|
| `--queue`, `-q` | `default` | Queue name to consume |
| `--concurrency`, `-c` | `1` | Concurrent task coroutines |
| `--poll-interval` | `1.0` | Seconds between database polls |
| `--max-tasks` | `0` (∞) | Stop after processing N tasks |

The worker exits cleanly on `SIGINT` / `SIGTERM`. See [Background Tasks](../topics/tasks.md).

## Version

```bash
buraq version
# Buraq 0.1.0
```

## Package management (uv wrappers)

```bash
buraq install requests httpx
buraq install --dev pytest
buraq uninstall requests
buraq sync
buraq pip freeze

# Run any command inside the uv virtual environment
buraq run python -m pytest
buraq run alembic history
```
