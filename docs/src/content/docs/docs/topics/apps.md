---
title: "App Registry"
description: "buraq.apps provides application configuration classes and a global registry — the same pattern as Django's AppConfig."
---

`buraq.apps` provides application configuration classes and a global registry — the same pattern as Django's `AppConfig`.

## AppConfig

`buraq startapp` writes an `apps.py` for you, with an empty `ready()` to fill
in. It is optional — an app listed by its own name works without one — and this
is what it looks like filled in:

```python
# blog/apps.py
from buraq.apps import AppConfig

class BlogConfig(AppConfig):
    name = "blog"
    verbose_name = "Blog"

    async def ready(self):
        import blog.signals  # connect signals on startup
```

Register it in `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    "blog.apps.BlogConfig",
    "shop",  # plain package path also accepted
]
```

Both forms behave the same. Given a package, Buraq imports `shop/apps.py` and uses
the `AppConfig` declared there; given a class path, it uses that class directly. If
an `apps.py` declares more than one config, mark the one to use:

```python
class ShopConfig(AppConfig):
    name = "shop"
    default = True
```

## AppConfig attributes

| Attribute | Description |
|---|---|
| `name` | Dotted Python path to the app module |
| `verbose_name` | Human-readable name (auto-generated from `label` if not set) |
| `label` | Short name used as dict key (defaults to last part of `name`) |
| `default` | Selects this config when the app's `apps.py` declares several |

## ready() hook

`ready()` runs once during startup, after every installed app's `models` module has
been imported, so the ORM registry is fully populated by the time it is called. Use
it to connect signals, register checks, or perform one-time initialization:

It only runs for an app registered by its config path, or one whose `apps.py`
declares a config — an app listed as a bare package with no `apps.py` has no
`ready()` to run.

```python
async def ready(self):
    from buraq.checks import register, Warning

    @register
    def check_stripe_key(settings, **kwargs):
        if not getattr(settings, "STRIPE_SECRET_KEY", None):
            return [Warning("STRIPE_SECRET_KEY is not set.", id="payments.W001")]
        return []
```

## Global registry

Buraq loads `INSTALLED_APPS` for you — on ASGI startup and before any management
command that sends a signal. You do not need to call `populate()` or
`run_ready_hooks()` yourself; both are idempotent, so calling them again is
harmless but does nothing.

```python
from buraq.apps import apps

config = apps.get_app_config("blog")
config.verbose_name  # "Blog"

apps.is_installed("blog")  # True
apps.get_app_configs()     # [BlogConfig, ...]
apps.ready                 # True once apps are loaded
```

## Loading Buraq outside the app

`configure()` loads the settings module and imports every installed app's models
from a synchronous entry point. It is what a migration run calls, and it suits any
standalone script that needs the ORM without starting the server:

```python
from buraq.apps import configure

configure()               # or configure("config.prod_settings")
```

It deliberately does not run `ready()` hooks — those are coroutines, and schema
work does not need them. Inside the running application, startup already handles
everything.

## Startup and shutdown hooks

To run your own code around startup, register it:

```python
app = Buraq(settings_module="config.settings")

@app.on_startup
async def warm_caches():
    await load_feature_flags()

@app.on_shutdown
async def flush():
    await metrics.flush()
```

Startup hooks run after the framework has loaded apps, run system checks and warmed
the template and translation caches. Shutdown hooks run in reverse registration
order, before the database engine is disposed, so they can still issue queries.

:::caution[Do not create tables here]
`create_tables()` builds the schema straight from your models, bypassing the
migration history entirely. Called on startup it hides an empty or outdated
history — the tables exist, so nothing looks wrong, until you deploy somewhere the
app has not run yet and `buraq migrate` produces an empty database. Let
[migrations](/docs/topics/orm/migrations) own the schema; `create_tables()` is for
tests and throwaway scripts.
:::

:::caution
Do not assign over `app._on_startup`. That method *is* the framework's startup —
replacing it silently drops app loading, system checks, template tag discovery and
translation warmup, and nothing reports that they were skipped.
:::
