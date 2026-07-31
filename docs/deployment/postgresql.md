# PostgreSQL

## Install the driver

```bash
uv add asyncpg
```

## Configure

```python title="config/settings.py"
DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/mydb"
```

Or from environment:

```python
import os
DATABASE_URL = os.environ["DATABASE_URL"]
```

## Create the database

```bash
psql -U postgres -c "CREATE DATABASE mydb;"
psql -U postgres -c "CREATE USER myuser WITH PASSWORD 'mypassword';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE mydb TO myuser;"
```

## Apply migrations

```bash
python manage.py migrate
```

## Connection pooling

The Buraq engine is pre-configured for PostgreSQL with:

- `pool_size = 10` — maintained connections
- `max_overflow = 20` — burst connections
- `pool_pre_ping = True` — validate connections before use

Adjust in settings if needed:

```python
DATABASE_POOL_SIZE     = 20
DATABASE_MAX_OVERFLOW  = 40
```

## DATABASE_URL formats

```
# Standard
postgresql+asyncpg://user:pass@localhost:5432/dbname

# With SSL
postgresql+asyncpg://user:pass@host:5432/dbname?ssl=require

# Unix socket
postgresql+asyncpg://user:pass@/dbname?host=/var/run/postgresql
```
