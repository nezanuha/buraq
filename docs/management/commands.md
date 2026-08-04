# Built-in Management Commands

All commands run via `buraq <command>`.

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

## Users

```bash
# Create a superuser interactively
buraq createsuperuser
```

## Apps & Projects

```bash
# Scaffold a new app
buraq startapp posts

# Scaffold a new project
buraq startproject myproject
buraq startproject myproject --postgres    # with PostgreSQL config
```

## Static files

```bash
buraq collectstatic
buraq collectstatic --dest /var/www/static
buraq collectstatic --clear       # wipe destination first
```

## Cache

```bash
buraq clearcache
```

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

## Package management (uv wrappers)

```bash
buraq install requests httpx
buraq install --dev pytest
buraq uninstall requests
buraq sync
buraq pip freeze
```
