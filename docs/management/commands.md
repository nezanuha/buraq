# Built-in Management Commands

All commands run via `python manage.py <command>`.

## Server

```bash
# Start development server (default: main:app on 127.0.0.1:8000)
python manage.py runserver

# Custom port (Django-style)
python manage.py runserver 8080

# Custom host:port
python manage.py runserver 0.0.0.0:8080

# Custom app path
python manage.py runserver config.urls:app

# Options
python manage.py runserver --no-reload      # disable auto-reload
python manage.py runserver --workers 4      # multiple workers (disables reload)
```

## Database

```bash
# Generate migration from model changes
python manage.py makemigrations
python manage.py makemigrations "add slug to post"

# Apply all pending migrations
python manage.py migrate

# Migrate to a specific revision
python manage.py migrate abc1234

# Roll back migrations
python manage.py rollback          # 1 migration
python manage.py rollback 3        # 3 migrations

# View migration history
python manage.py showmigrations
```

## Users

```bash
# Create a superuser interactively
python manage.py createsuperuser
```

## Apps & Projects

```bash
# Scaffold a new app
python manage.py startapp posts

# Scaffold a new project
buraq startproject myproject
buraq startproject myproject --postgres    # with PostgreSQL config
```

## Static files

```bash
python manage.py collectstatic
python manage.py collectstatic --dest /var/www/static
python manage.py collectstatic --clear       # wipe destination first
```

## Cache

```bash
python manage.py clearcache
```

## Package management (uv wrappers)

```bash
python manage.py install requests httpx
python manage.py install --dev pytest
python manage.py uninstall requests
python manage.py sync
python manage.py pip freeze
```
