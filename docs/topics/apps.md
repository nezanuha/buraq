# App Registry

`buraq.apps` provides application configuration classes and a global registry — the same pattern as Django's `AppConfig`.

## AppConfig

Create an `apps.py` in your application:

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
    "shop",  # plain string also accepted
]
```

## AppConfig attributes

| Attribute | Description |
|---|---|
| `name` | Dotted Python path to the app module |
| `verbose_name` | Human-readable name (auto-generated from `label` if not set) |
| `label` | Short name used as dict key (defaults to last part of `name`) |

## ready() hook

`ready()` is called after all apps are loaded. Use it to connect signals, register checks, or perform one-time initialization:

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

```python
from buraq.apps import apps

# Populate from settings
apps.populate(settings.INSTALLED_APPS)

# Run all ready() hooks
await apps.run_ready_hooks()

# Query the registry
config = apps.get_app_config("blog")
config.verbose_name  # "Blog"

apps.is_installed("blog")  # True
apps.get_app_configs()     # [BlogConfig, ...]
apps.ready                 # True after populate()
```
