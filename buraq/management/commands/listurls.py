"""
listurls — list all URL patterns registered in the project's root URLconf.

Usage:
    python manage.py listurls
    python manage.py listurls --urlconf config.urls
"""
from buraq.management.base import BaseCommand


class Command(BaseCommand):
    help = "List all URL patterns from the project's root URLconf."

    def add_arguments(self, parser):
        parser.add_argument(
            "--urlconf",
            default=None,
            help="Python path to the URLconf module (default: settings.ROOT_URLCONF).",
        )

    async def handle(self, *args, **options):
        import importlib
        from buraq.conf import settings

        urlconf_module = options["urlconf"] or getattr(settings, "ROOT_URLCONF", None)
        if not urlconf_module:
            self.stderr.write(self.style.ERROR("No ROOT_URLCONF set and --urlconf not provided."))
            return

        try:
            module = importlib.import_module(urlconf_module)
        except ImportError as exc:
            self.stderr.write(self.style.ERROR(f"Cannot import URLconf {urlconf_module!r}: {exc}"))
            return

        urlpatterns = getattr(module, "urlpatterns", [])
        if not urlpatterns:
            self.stdout.write("No URL patterns found.")
            return

        rows = []
        _collect(urlpatterns, prefix="", rows=rows)

        col_w = max((len(r[0]) for r in rows), default=4)
        name_w = max((len(r[2]) for r in rows), default=4)

        header = f"{'Path':<{col_w}}  {'View':<40}  {'Name':<{name_w}}"
        self.stdout.write(self.style.MIGRATE_HEADING(header))
        self.stdout.write("-" * len(header))
        for path, view, name in rows:
            self.stdout.write(f"{path:<{col_w}}  {view:<40}  {name:<{name_w}}")


def _collect(patterns, prefix: str, rows: list) -> None:
    for pattern in patterns:
        # starlette / buraq Route
        route_path = getattr(pattern, "path", None) or getattr(pattern, "pattern", "")
        full_path = prefix + str(route_path)

        # Included sub-router
        sub_routes = getattr(pattern, "routes", None)
        if sub_routes is not None:
            _collect(sub_routes, full_path, rows)
            continue

        # URLInclude (buraq.urls.include)
        included = getattr(pattern, "urlconf", None)
        if included is not None:
            import importlib
            sub_mod = importlib.import_module(included) if isinstance(included, str) else included
            sub_patterns = getattr(sub_mod, "urlpatterns", [])
            _collect(sub_patterns, full_path, rows)
            continue

        # Leaf pattern
        endpoint = getattr(pattern, "endpoint", None) or getattr(pattern, "callback", None)
        if endpoint is None:
            continue

        if hasattr(endpoint, "__name__"):
            view_name = f"{endpoint.__module__}.{endpoint.__name__}"
        elif hasattr(endpoint, "__class__"):
            view_name = f"{endpoint.__class__.__module__}.{endpoint.__class__.__name__}"
        else:
            view_name = str(endpoint)

        name = getattr(pattern, "name", "") or ""
        rows.append((full_path, view_name, name))
