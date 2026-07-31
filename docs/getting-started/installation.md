# Installation

## Requirements

- **Python 3.11+**
- An async database driver (pick one based on your database)

## Install Buraq

=== "uv (recommended)"

    ```bash
    uv add buraq
    ```

=== "pip"

    ```bash
    pip install buraq
    ```

## Install a Database Driver

Buraq uses SQLAlchemy's async engine. Install the driver that matches your database:

=== "SQLite (development)"

    ```bash
    uv add aiosqlite
    ```

=== "PostgreSQL (production)"

    ```bash
    uv add asyncpg
    ```

=== "MySQL / MariaDB"

    ```bash
    uv add aiomysql
    # or
    uv add "buraq[mysql]"
    ```

## Optional Extras

```bash
# Memcached cache backend
uv add aiomcache

# Redis cache backend
uv add "redis[hiredis]"

# Production server
uv add "buraq[production]"   # installs gunicorn + whitenoise
```

## Verify Installation

```bash
python -c "import buraq; print(buraq.__version__)"
```

## Create Your First Project

```bash
buraq startproject myproject
cd myproject
uv sync
python manage.py migrate
python manage.py runserver
```

!!! tip
    `python manage.py runserver` auto-detects the `.venv` in your project folder and uses it — no manual activation needed.
