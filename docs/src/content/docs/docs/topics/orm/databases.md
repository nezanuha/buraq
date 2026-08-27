---
title: Databases
description: Supported backends, connection options, and what each one does differently.
---

Buraq talks to a database through SQLAlchemy's async engine, so the driver has to
be one that can be awaited. That is the whole of the compatibility rule; the rest
of this page is what each backend does differently.

## Supported backends

| Backend | Driver | Install | Notes |
|---|---|---|---|
| SQLite | `aiosqlite` | included | the default; see [SQLite](#sqlite) before using it in production |
| PostgreSQL | `asyncpg` | `pip install buraq[postgres]` | the one to reach for in production |
| MySQL | `aiomysql` | `pip install buraq[mysql]` | |
| MariaDB | `aiomysql` | `pip install buraq[mysql]` | uses the MySQL dialect |

Buraq pins no minimum server version of its own: what works is what SQLAlchemy
2.0 and the driver support, and those are the projects to check against.

```python title="config/settings.py"
DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/mydb"
```

The `+driver` part is required. A URL without it selects a blocking driver and is
refused at startup — see [Settings](../../getting-started/settings.md#database).

:::note[What is actually tested]
CI runs the whole suite three times: against SQLite on Linux, Windows and macOS,
and against a real PostgreSQL and a real MySQL server on Linux. MariaDB is not
in CI — it uses the same dialect and driver as MySQL, which is the reason to
expect it to work and not a substitute for testing it.

Treat the notes below as the differences known to bite, not as an exhaustive
list, and run your own suite against the backend you deploy on.
:::

### Everything else

Whether another database is reachable at all is decided by SQLAlchemy, not by
Buraq: it needs an *async* dialect, and most do not have one.

| | | |
|---|---|---|
| CockroachDB | `postgresql+asyncpg` | speaks the PostgreSQL wire protocol |
| YugabyteDB | `postgresql+asyncpg` | speaks the PostgreSQL wire protocol |
| TiDB | `mysql+aiomysql` | speaks the MySQL wire protocol |
| SQL Server | `mssql+aioodbc` | an async dialect exists |
| **Oracle** | — | **no async dialect in SQLAlchemy 2.0** |
| **Firebird** | — | community dialect, synchronous only |
| **Cloud Spanner** | — | community dialect, synchronous only |
| **Snowflake** | — | community dialect, synchronous only |
| **MongoDB** | — | not SQL; SQLAlchemy does not address it |

The first four will connect. Nothing more than that is claimed: the wire
protocol matching is what lets a driver talk to them, and it says nothing about
whether the SQL Buraq generates or the migrations it writes behave the same way.
If you deploy on one of these, your own test suite is the only thing that will
tell you.

The rest cannot work today at any level of effort inside Buraq — a synchronous
driver cannot be awaited, and there is nothing to configure that changes it.
`oracledb` does ship an asyncio mode, but SQLAlchemy 2.0 exposes no async Oracle
dialect to reach it through.
:::note
Buraq's driver check leaves backends it does not recognise alone, so an
unrecognised URL is passed to SQLAlchemy rather than rejected — you get
SQLAlchemy's own error, which is the accurate one.
:::

## Configurations

Every shape, shortest first. All of these go in `config/settings.py`.

### One database

```python
# SQLite — the default; a new project needs none of this
DATABASE_URL = "sqlite+aiosqlite:///./db.sqlite3"

# PostgreSQL
DATABASE_URL = "postgresql+asyncpg://user:pass@localhost:5432/mydb"

# MySQL or MariaDB
DATABASE_URL = "mysql+aiomysql://user:pass@localhost:3306/mydb"
```

### One database, tuned

```python
# SQLite, when writers overlap and you get "database is locked"
DATABASE_OPTIONS = {"connect_args": {"timeout": 20}}

# PostgreSQL with a larger pool and stricter isolation
DATABASE_OPTIONS = {
    "pool_size": 30,
    "max_overflow": 10,
    "isolation_level": "SERIALIZABLE",
}

# PostgreSQL behind PgBouncer in transaction mode — required, not optional
DATABASE_OPTIONS = {"connect_args": {"statement_cache_size": 0}}
```

### A read replica

```python
DATABASES = {
    "default": "postgresql+asyncpg://user:pass@primary/db",
    "replica": "postgresql+asyncpg://user:pass@replica/db",
}
DATABASE_READ_REPLICAS = ["replica"]
```

Reads go to `replica`, writes to `default`, and nothing in your queries changes.

### Several replicas, sized separately

```python
DATABASES = {
    "default": {"URL": "postgresql+asyncpg://u:p@primary/db",
                "OPTIONS": {"pool_size": 10}},
    "eu":      {"URL": "postgresql+asyncpg://u:p@eu/db",
                "OPTIONS": {"pool_size": 40}},
    "us":      {"URL": "postgresql+asyncpg://u:p@us/db",
                "OPTIONS": {"pool_size": 40}},
}
DATABASE_READ_REPLICAS = ["eu", "us"]
```

Reads rotate between `eu` and `us`. The replicas take the read traffic, so they
get the larger pools.

### A second database, no automatic routing

```python
DATABASES = {
    "default": "postgresql+asyncpg://u:p@main/db",
    "legacy":  "mysql+aiomysql://u:p@old/db",
}
```

With no `DATABASE_READ_REPLICAS`, everything goes to `default` and the second is
reached only when asked for:

```python
await LegacyRow.objects.using("legacy").filter(archived=False)
```

Note the backends differ — nothing requires them to match.

### From the environment

`DATABASE_URL` is read from the environment before the value in the file, so a
deployment redirects it without an edit:

```python
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./db.sqlite3")
```

This is what a scaffolded project already has. `DATABASES` has no equivalent —
build it from `os.environ` yourself if a deployment needs to vary it.

### Two mistakes, and what they say

```python
DATABASES = {"default": "postgresql+asyncpg://u:p@main/db"}
DATABASE_READ_REPLICAS = ["replica"]
```
```
ImproperlyConfigured: DATABASE_READ_REPLICAS names ['replica'], which
DATABASES does not define. Known: default.
```

```python
DATABASE_URL = "postgresql://user:pass@localhost/mydb"
```
```
ImproperlyConfigured: DATABASE_URL is 'postgresql', which selects a blocking
driver. Buraq is async throughout, so the driver has to be one that can be
awaited.

Use:  postgresql+asyncpg://...
```

## Connection options

`OPTIONS` is handed to SQLAlchemy's engine, so anything it or the driver accepts
can be set without Buraq needing a name for it:

```python title="config/settings.py"
DATABASE_URL     = "postgresql+asyncpg://user:password@localhost/mydb"
DATABASE_OPTIONS = {
    "pool_size": 20,
    "isolation_level": "SERIALIZABLE",
    "connect_args": {"statement_cache_size": 0},
}
```

With several databases it goes per alias, which is usually what you want — a
replica taking all the reads wants a larger pool than the primary:

```python title="config/settings.py"
DATABASES = {
    "default": {
        "URL": "postgresql+asyncpg://user:pass@primary/db",
        "OPTIONS": {"pool_size": 20},
    },
    "replica": {
        "URL": "postgresql+asyncpg://user:pass@replica/db",
        "OPTIONS": {"pool_size": 50},
    },
}
```

`connect_args` is merged with what Buraq sets rather than replacing it, so
SQLite's `check_same_thread` survives an entry of your own.

### Pooling

| setting | default | |
|---|---|---|
| `DATABASE_POOL_SIZE` | 10 | connections kept open |
| `DATABASE_MAX_OVERFLOW` | 20 | extra connections under load |
| `DATABASE_POOL_RECYCLE` | 3600 | seconds before a connection is retired |

Connections are pooled and health-checked (`pool_pre_ping`) by default. There is
no per-request connection setting to tune, and deliberately so: a persistent
connection per request is a threaded model, and an async server runs thousands
of concurrent tasks rather than a handful of threads.

`DATABASE_POOL_RECYCLE` matters most on MySQL, which closes an idle connection
after eight hours. Retiring it first is cheaper than discovering it is gone.

SQLite ignores all three — it reuses a single connection.

## SQLite

Fine for development, and for a read-mostly site on one process. Its limits are
about concurrent *writers*:

**"database is locked"** means writers overlapped. Keep transactions short, or
raise the wait:

```python
DATABASE_OPTIONS = {"connect_args": {"timeout": 20}}
```

**`select_for_update()` does nothing.** SQLite has no `SELECT ... FOR UPDATE`,
and the clause is dropped from the statement rather than raising:

```sql
-- what Buraq asks for            -- what SQLite runs
SELECT t.id FROM t FOR UPDATE     SELECT t.id FROM t
```

So code relying on it for correctness is wrong on SQLite while appearing to
work, and only fails under load.

**No real decimal type.** `DecimalField` is stored as an 8-byte float, so money
arithmetic will not round the way it does on PostgreSQL or MySQL.

**Substring matching is case-insensitive** for ASCII, and `iexact` behaves like
`exact` for non-ASCII.

## PostgreSQL

The backend with the fewest surprises, and the one to reach for in production.

**Behind PgBouncer in transaction mode**, asyncpg's prepared statements break —
each transaction may land on a different server connection. Turn the cache off:

```python
DATABASE_OPTIONS = {"connect_args": {"statement_cache_size": 0}}
```

This is not optional; without it you get errors that look random.

**Isolation level** defaults to `READ COMMITTED`:

```python
DATABASE_OPTIONS = {"isolation_level": "SERIALIZABLE"}
```

**`iterator()` streams** rather than loading every row, so a large scan does not
cost memory proportional to the result.

## MySQL and MariaDB

**Use InnoDB.** MyISAM has no transactions and no foreign keys, so `atomic()`
silently does nothing.

**Create the database as `utf8mb4`**, not `utf8` — the latter is three bytes and
cannot store every character:

```sql
CREATE DATABASE mydb CHARACTER SET utf8mb4;
```

**`unique=True` on a long `CharField` fails.** An indexed `VARCHAR` is limited to
255 characters. Shorten the field, or drop the constraint and enforce it in the
application.

**`TextField` cannot be indexed or made unique.** MySQL will not index a `TEXT`
column without a prefix length.

**`select_for_update()` is partial** — `SKIP LOCKED`, `NOWAIT` and `OF` are not
available, and a `SELECT ... FOR UPDATE` that does not use an index locks the
whole table.

**Idle connections are dropped after eight hours.** `DATABASE_POOL_RECYCLE`
already handles this; do not raise it above `wait_timeout`.
